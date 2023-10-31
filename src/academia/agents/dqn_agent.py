from collections import deque, namedtuple
from typing import Type, Optional
import os
import zipfile
import tempfile
import json

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

from academia.agents.base import Agent

USE_CUDA = torch.cuda.is_available()
device = torch.device("cuda" if USE_CUDA else "cpu")


class DQNAgent(Agent):
    """
    Class representing a Deep Q-Network (DQN) agent for reinforcement learning tasks.

    The DQNAgent class implements the Deep Q-Network (DQN) algorithm for reinforcement learning tasks.
    It uses a neural network to approximate the Q-values of actions in a given environment. The agent
    learns from experiences stored in a replay memory and performs updates to its Q-values during
    training episodes. The target network is soft updated to stabilize training.

    Args:
        nn_architecture: Type of neural network architecture to be used.
        n_actions: Number of possible actions in the environment.
        gamma: Discount factor for future rewards (default: 0.99).
        epsilon: Initial exploration-exploitation trade-off parameter (default: 1.0).
        epsilon_decay: Decay factor for epsilon over time (default: 0.995).
        min_epsilon: Minimum epsilon value to ensure exploration (default: 0.01).
        batch_size: Size of the mini-batch used for training (default: 64).
        random_state: Seed for random number generation (default: None).

    Examples:
        ```python
        # Example Usage of DQNAgent

        from models import CartPoleMLP  # Import custom neural network architecture
        
        # Create an instance of the DQNAgent class with custom neural network architecture
        dqn_agent = DQNAgent(nn_architecture=CartPoleMLP, n_actions=2, gamma=0.99, epsilon=1.0,
                             epsilon_decay=0.99, min_epsilon=0.01, batch_size=64)
        
        # Training loop: Update the agent using experiences (state, action, reward, next_state, done)
        for episode in range(num_episodes):
            state = env.reset()
            done = False
            while not done:
                action = dqn_agent.get_action(state)
                next_state, reward, terminated, truncated, info = env.step(action)
                if terminated or truncated:
                    done = True 
                dqn_agent.update(state, action, reward, next_state, done)
                state = next_state
        ```
    Note:
        - Ensure that the custom neural network architecture passed to the constructor inherits 
          from torch.nn.Module and is appropriate for the task.
        - The agent's exploration-exploitation strategy is based on epsilon-greedy method.
        - The __soft_update_target method updates the target network weights from the main network's weights
        based on strategy target_weights = TAU * main_weights + (1 - TAU) * target_weights, where TAU << 1.
        - It is recommended to adjust hyperparameters such as gamma, epsilon, epsilon_decay, and batch_size
          based on the specific task and environment.
    """
    REPLAY_MEMORY_SIZE:int = 100000
    """Maximum size of the replay memory."""
    LR:float = 0.0005
    """Learning rate for the optimizer."""
    TAU:float = 0.001  # interpolation parameter
    """Interpolation parameter for target network updates."""
    UPDATE_EVERY:int = 3
    """Frequency of target network updates."""

    def __init__(self, nn_architecture: Type[nn.Module],
                 n_actions: int,
                 gamma: float = 0.99, epsilon: float = 1.,
                 epsilon_decay: float = 0.995,
                 min_epsilon: float = 0.01,
                 batch_size: int = 64, random_state: Optional[int] = None
                 ):
        """
        Initializes a new instance of the DQNAgent class.

        Args:
            nn_architecture: Type of neural network architecture to be used.
            n_actions: Number of possible actions in the environment.
            gamma: Discount factor for future rewards (default: 0.99).
            epsilon: Initial exploration-exploitation trade-off parameter (default: 1.0).
            epsilon_decay: Decay factor for epsilon over time (default: 0.995).
            min_epsilon: Minimum epsilon value to ensure exploration (default: 0.01).
            batch_size: Size of the mini-batch used for training (default: 64).
            random_state: Seed for random number generation (default: None).
        """
        super(DQNAgent, self).__init__(epsilon=epsilon, min_epsilon=min_epsilon,
                                       epsilon_decay=epsilon_decay,
                                       n_actions=n_actions, gamma=gamma, random_state=random_state)
        self.memory = deque(maxlen=self.REPLAY_MEMORY_SIZE)
        self.batch_size = batch_size
        self.nn_architecture = nn_architecture
        self.experience = namedtuple("Experience", field_names=["state","action",
                                                                "reward", "next_state", "done"])
        self.train_step = 0
        
        if random_state is not None:
            torch.manual_seed(random_state)
        self.__build_network()
        self.optimizer = optim.Adam(self.network.parameters(), lr=5e-4)

    def __build_network(self):
        """
        Builds the neural network architectures for both the main and target networks.

        The method creates instances of the neural network specified by nn_architecture and
        initializes the optimizer with the Adam optimizer. It also initializes the target
        network with the same architecture and loads its initial weights from the main
        network. The target network is set to evaluation mode during training.

        Note:
            - The neural networks are moved to the appropriate device (CPU or CUDA) using the to(device) method.
            - The target network is initialized with the same architecture as the main network with same weights.
        """
        self.network = self.nn_architecture()
        self.network.to(device)

        self.target_network = self.nn_architecture()
        self.target_network.to(device)

        self.optimizer = optim.Adam(self.network.parameters(), lr=self.LR)

    def __remember(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        """
        Stores an experience tuple in the replay memory.

        Args:
            state: Current state of the agent in the environment.
            action: Action taken by the agent in the current state.
            reward: Reward received by the agent after taking the action.
            next_state: Next state of the agent after taking the action.
            done: A boolean flag indicating if the episode has terminated or truncated after the action.
        """
        e = self.experience(state, action, reward, next_state, done)
        self.memory.append(e)

    def get_action(self, state: np.ndarray, legal_mask: np.ndarray =None, greedy=False) -> int:
        """
        Selects an action based on the current state using the epsilon-greedy strategy.

        Args:
            state: The current state representation used to make the action selection decision.
            legal_mask: A binary mask indicating the legality of actions.
                If provided, restricts the agent's choices to legal actions.
            greedy: A boolean flag indicating whether to force a greedy action selection.
                If True, the function always chooses the action with the highest Q-value, ignoring exploration.

        Returns:
            The index of the selected action.
        """
        state = torch.from_numpy(state).float().to(device)
        self.network.eval()

        with torch.no_grad():
            q_val_act = self.network(state).to(device)
        self.network.train()

        if legal_mask is not None:
            legal_mask = torch.from_numpy(legal_mask).float().to(device)
            q_val_act = (q_val_act - torch.min(q_val_act)) * legal_mask \
                + legal_mask
            
        if self._rng.uniform() > self.epsilon or greedy:
            return torch.argmax(q_val_act).item()
        
        elif legal_mask is not None:
            legal_mask_cpu = torch.Tensor.cpu(legal_mask)
            return \
            self._rng.choice(np.arange(0, self.n_actions), size=1, p=legal_mask_cpu/legal_mask_cpu.sum())[
                0]
        else:
            return self._rng.integers(0, self.n_actions)

    def __soft_update_target(self):
        """
        Updates the target network's weights with the main network's weights.

        It uses soft max strategy so target_weights = TAU * main_weights + (1 - TAU) * target_weights, where TAU << 1.
        Small value of Tau still covers the statement that target values supposed to be fixed to prevent moving target problem
        """
        for network_params, target_params in zip(self.network.parameters(), 
                                                 self.target_network.parameters()):
            target_params.data.copy_(self.TAU * network_params.data \
                                     + (1.0 - self.TAU) * target_params.data)

    def update(self, state: np.ndarray, action: int, reward: float, new_state: np.ndarray, is_terminal: bool):
        """
        Updates the DQN network weights to better estimate Q-values of every action.

        Args:
            state: Current state of the environment.
            action: Action taken in the current state.
            reward: Reward received after taking the action.
            new_state: Next state of the environment after taking the action.
            is_terminal: A flag indicating whether the new state is a terminal state.
        """
        self.__remember(state=state, action=action, reward=reward, next_state=new_state,
                      done=is_terminal)
        self.train_step = (self.train_step + 1) % self.UPDATE_EVERY
        if self.train_step == 0:
            if len(self.memory) >= self.batch_size:
                states, actions, rewards, next_states, dones = self.__replay()
                q_targets_next = self.target_network(next_states).detach().max(1)[0].unsqueeze(1)
                # bellman equation
                q_targets = rewards + self.gamma * q_targets_next * (1 - dones)
                q_expected = self.network(states).gather(1, actions)
                loss = F.mse_loss(q_expected, q_targets)
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                self.__soft_update_target()

    def __replay(self) -> (torch.Tensor, torch.Tensor):
        """
        Samples a mini-batch from the replay memory and prepares states, actions, rewards, next_states
        casting them to tensors with appropriate type values and adding to device.

        Returns:
            Tuple containing tensors of states, actions, rewards, next_states, and dones.
        """
        batch_indices = self._rng.choice(len(self.memory), size=self.batch_size, replace=False)
        batch = [self.memory[i] for i in batch_indices]
        states = torch.from_numpy(np.vstack([e.state for e in batch if e is not None])).float().to(device)
        actions = torch.from_numpy(np.vstack([e.action for e in batch if e is not None])).long().to(device)
        rewards = torch.from_numpy(np.vstack([e.reward for e in batch if e is not None])).float().to(device)
        next_states = torch.from_numpy(np.vstack([e.next_state for e in batch if e is not None]))\
            .float().to(device)
        dones = torch.from_numpy(np.vstack([e.done for e in batch if e is not None])).float().to(device)
        return (states, actions, rewards, next_states, dones)

    def save(self, path: str) -> str:
        """
        Saves the state dictionary of the neural network model to the specified file path.

        Args:
            path: The file path (including filename and extension) where the model's state dictionary will be saved.

        Returns:
            Absolute path to the saved file.
        """
        if not path.endswith('.zip'):
            path += '.agent.zip'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with zipfile.ZipFile(path, 'w') as zf:
            # network state
            network_temp = tempfile.NamedTemporaryFile()
            torch.save(self.network.state_dict(), network_temp)
            # agent config
            agent_temp = tempfile.NamedTemporaryFile()
            learner_state_dict = {
                'n_actions': self.n_actions,
                'gamma': self.gamma,
                'epsilon': self.epsilon,
                'epsilon_decay': self.epsilon_decay,
                'min_epsilon': self.min_epsilon,
                'batch_size': self.batch_size,
                'nn_architecture': self.get_type_name_full(self.nn_architecture),
                'random_state': self._rng.bit_generator.state
            }
            with open(agent_temp.name, 'w') as file:
                json.dump(dict(learner_state_dict), file, indent=4)
            # zip both
            zf.write(network_temp.name, 'network.pth')
            zf.write(agent_temp.name, 'state.agent.json')
        return os.path.abspath(path)

    @classmethod
    def load(cls, path: str) -> 'DQNAgent':
        """
        Loads the state dictionary of the neural network model from the specified file path. 

        Parameters:
            - path: The file path from which to load the model's state dictionary.
        """
        if not path.endswith('.zip'):
            path += '.agent.zip'
        zf = zipfile.ZipFile(path)
        with tempfile.TemporaryDirectory() as tempdir:
            zf.extractall(tempdir)
            # network state
            network_params = torch.load(os.path.join(tempdir, 'network.pth'))
            # agent config
            with open(os.path.join(tempdir, 'state.agent.json'), 'r') as file:
                params = json.load(file)

        nn_architecture = cls.get_type(params['nn_architecture'])
        del params['nn_architecture']
        rng_state = params.pop('random_state')
        agent = cls(nn_architecture=nn_architecture, **params)
        agent._rng.bit_generator.state = rng_state
        agent.network.load_state_dict(network_params)
        agent.target_network.load_state_dict(network_params)
        return agent
