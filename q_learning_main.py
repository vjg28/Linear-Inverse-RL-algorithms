"""
This code basically contains 
    a) The code/functions of RL part of the IRL code.
        * This RL code takes in reward function and returns the new learnt policy.
    b) The code for generating expert polices and trajectories.
        ** The expert policies are generally displayed by some human or machine who is an expert in that activity. 
        Here, we used a different approach to learn expert policy. 
        We used RL algorithm (Q-learning with Linear Function Approximation) to train an agent to be an expert in Mountain Car env. 
        And then, that learnt agent is considered as an expert and the expert trajectories are generated by that agent.
"""
import gym
import itertools
import numpy as np
import sklearn.pipeline
import sklearn.preprocessing
from sklearn.linear_model import SGDRegressor
from sklearn.kernel_approximation import RBFSampler
from collections import defaultdict
import plotting
import matplotlib.pyplot as plt
from tqdm import tqdm



# For Q learning code
# Container for feature vector of RL part
def state_featurizer(normalized_data):
    featurizer=sklearn.pipeline.FeatureUnion([
        ("rbf1", RBFSampler(gamma=5.0, n_components=100)),
        ("rbf2", RBFSampler(gamma=2.0, n_components=100)),
        ("rbf3", RBFSampler(gamma=1.0, n_components=100)),
        ("rbf4", RBFSampler(gamma=0.5, n_components=100))
    ])
    featurizer.fit(normalized_data)
    return featurizer


class Estimator():
    """
    Value function approximator
    """
    
    def __init__(self,env,scaler,featurizer):
        # We create individual models for each action instead of getting 
        # output as a nA*1 vector.
        self.models=[]
        self.env = env
        self.scaler = scaler
        self.featurizer=featurizer
        for _ in range(3):
            model=SGDRegressor(learning_rate="constant", max_iter = 200000000, tol= 1e-10)
            # We need to call partial_fit once to initialize the model
            # or we get a NotFittedError when trying to make a prediction
            # This is quite hacky.
            model.partial_fit([self.featurize_state(self.env.reset())],[0])
            self.models.append(model)
    
    def featurize_state(self, state):
        
        scaled= self.scaler.transform([state])
        featurized= self.featurizer.transform(scaled)
        return featurized[0]
    
    def predict(self, s, a=None):
        # Makes value function predictions.
        
        feature_vec= self.featurize_state(s)
        if not a:
            return np.array([m.predict([feature_vec]) for m in self.models])
        else:
            return self.models[a].predict([feature_vec])      #.predict module is inbuilt in SGDRegresssor
    
    def update(self, s, a, y):
        """
        Updates the estimator parameters for a given state and action towards
        the target y.
        """
        feature_vec = self.featurize_state(s)
        (self.models[a]).partial_fit([feature_vec], [y])
        

def epsilon_greedy_policy(observation,estimator, epsilon, nA):
    # Returns a e-greeedy policy
    
    A=np.ones(nA, dtype=float) * epsilon / nA
    q_values=  estimator.predict(observation)
    best_action=np.argmax(q_values)
    A[best_action] += (1.0 - epsilon)
    return A

def greedy_policy(estimator, nA):
    # returns a function for generating greedy policy for a state/observation.
    def policy_maker(observation):
        A=np.zeros(nA, dtype=float)
        q_values=  estimator.predict(observation)
        best_action=np.argmax(q_values)
        A[best_action] += (1.0)
        return A
    return policy_maker

def policy_f(env, scaler,featurizer,print_ep_lens):
    '''
    Main Calling Function for generating expert policy.
    ** Read the multi-line comment at the starting of this file to gain understanding.
    
    Args:
        env: Gym environment
        scaler: Mean and variance of the state values.
        featurizer: The container used for generating expert trajectories.
        print_ep_stats: [Bool] Prints interation with no. of time steps required for completion
        
    Returns:
        a) Plots statisics of mountain car learning with inbuilt rewards in the gym environment.
        So that we are able to compare results with the mountain car learning with learnt reward function.
        b) Returns "Demostration By Expert" DBE policy.
    '''
    estimator= Estimator(env,scaler,featurizer)
    stats =  q_learning_best_policy(env, estimator, 200, epsilon = 0.0, print_ep_lens=False)
    print("___Plotting Learning Stats of the Agent____")
    plotting.plot_cost_to_go_mountain_car(env, estimator)
    plotting.plot_episode_stats(stats, smoothing_window=25)
    final_policy = greedy_policy(estimator, env.action_space.n)
    return final_policy, estimator
    

def q_learning(env, estimator, reward_fn, num_episodes, num_trajectory=0, discount_factor=1.0, epsilon=0.0, epsilon_decay=1.0, print_ep_details=False):
    """
    a) Given a reward function, this RL algorithm learns the policy for the environment.
    """
    d_vec=np.ones(num_episodes)*2000
    for i in tqdm(range(num_episodes)):
        state =env.reset()
        done= False
        
        '''Important: Breaking up the trajectory after 2000 timesteps,if not reached the goal during training.'''
        for d in range(2000):
            
            prob = epsilon_greedy_policy(state ,estimator, epsilon * epsilon_decay**i ,env.action_space.n)
            action = np.random.choice(np.arange(len(prob)), p=prob )
            step= env.step(action)
            
            next_state = step[0]
            done = step[2]
            if done:
                break
            reward = reward_fn(state)    
            q_values_next = estimator.predict(next_state)
            td_target = reward + discount_factor * np.max(q_values_next)
            estimator.update(state,action,td_target)
            state=next_state
        if print_ep_details:    
            print("Episode {} completed in {} timesteps".format(i,d))
        d_vec[i] = d 
    return np.min(d_vec)     # Just for some experiments: Not used anywhere in the IRL code. 



def q_learning_best_policy(env, estimator, num_episodes, discount_factor=1.0, epsilon=0.0, epsilon_decay=1.0, print_ep_lens=False):
    '''
    ** RL Code for the learning part of the expert agent. This does not take the reward function.
    It uses the default environment reward function.
    '''
    # Statistics during learning process
    stats= plotting.EpisodeStats(episode_lengths= np.zeros(num_episodes), episode_rewards = np.zeros(num_episodes))
    
    for i in tqdm(range(num_episodes)):
        state =env.reset()
        done= False
        d=0
        while not done:
            
            prob = epsilon_greedy_policy(state ,estimator, epsilon * epsilon_decay**i ,env.action_space.n)
            action = np.random.choice(np.arange(len(prob)), p=prob )
            next_state, reward, done, _ = env.step(action)
            
            stats.episode_rewards[i] += reward
            stats.episode_lengths[i] += 1
            
            q_values_next = estimator.predict(next_state)
            td_target = reward + discount_factor * np.max(q_values_next)
            estimator.update(state,action,td_target)
            state=next_state
            d+=1
        if print_ep_lens:
             print("Episode {} completed in {} timesteps".format(i,d))
    
    return stats        


def q_learning_testing_rewards(env, estimator, reward_fn, num_episodes, discount_factor=1.0,
                               epsilon=0.0, epsilon_decay=1.0, render=False,ep_details=False):
    '''
    Given the reward function, The RL agent learns the best policy.
    (Used for generating final results to compare with learning with default handcrafted rewards.) 
    '''
    # Statistics during learning process
    stats= plotting.EpisodeStats(episode_lengths= np.zeros(num_episodes), episode_rewards = np.zeros(num_episodes))
    
    for i in tqdm(range(num_episodes)):
        state = env.reset()
        done = False
        d = 0
        
        while not done and d<=2000:
            
            prob = epsilon_greedy_policy(state ,estimator, epsilon * epsilon_decay**i ,env.action_space.n)
            action = np.random.choice(np.arange(len(prob)), p=prob )
            step= env.step(action)
            
            next_state = step[0]
            done = step[2]
            reward = reward_fn(state)
            if render:
                env.render()
            
            stats.episode_rewards[i] += reward
            stats.episode_lengths[i] += 1
            
            q_values_next = estimator.predict(next_state)
            td_target = reward + discount_factor * np.max(q_values_next)
            estimator.update(state,action,td_target)
            state=next_state
            d+=1
        
        if ep_details:
            print("Episode {} completed in {} timesteps".format(i,d))   
    
    return stats        

def compare_results(env,estimator_f,estimator_dbe,num_test_trajs,epsilon_test=0.0):
    dbe_score=0
    imitator_score=0
    for network,point in [(estimator_dbe,1),(estimator_f,2)]: 
        tot_reward=np.zeros(num_test_trajs)
        for i in tqdm(range(num_test_trajs)):
            state=env.reset()
            done=False
            for t in range(2000):
                prob = epsilon_greedy_policy(state ,network, epsilon_test ,env.action_space.n)
                action= np.random.choice(np.arange(len(prob)),p=prob)
                next_state,reward,done,_= env.step(action)
                env.render()
                tot_reward[i]+=reward
                if done:
                    break
                state=next_state
                
        if point==1:
            dbe_score= np.sum(tot_reward)/num_test_trajs
        elif point==2:
            imitator_score = np.sum(tot_reward)/num_test_trajs
        else:
            print("Somethings wrong:(")
    
    plt.plot([1,2,3],[dbe_score]*3,label='DBE Score value')
    plt.plot([1,2,3],[imitator_score]*3,label='Imitator Score')
    plt.legend(loc='lower right')
    plt.xlabel("Just for reward visualization.[x axis is nothing]")
    plt.ylabel("Avg Reward")
    plt.show()
    env.close()
    print("Expert policy score  "+" | ",dbe_score)
    print("Imitator policy score"+" | ",imitator_score)
    return dbe_score, imitator_score
