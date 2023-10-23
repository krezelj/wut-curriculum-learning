import os
import logging

import yaml
import numpy as np

from . import LearningTask
from academia.agents.base import Agent
from academia.utils import SavableLoadable, Stopwatch


_logger = logging.getLogger('academia.curriculum')


class Curriculum(SavableLoadable):

    __slots__ = ['tasks']

    def __init__(self, tasks: list[LearningTask]) -> None:
        self.tasks = tasks

    def run(self, agent: Agent, verbose=0, render=False):
        total_episodes = 0
        stopwatch = Stopwatch()
        for i, task in enumerate(self.tasks):
            if verbose >= 1:
                _logger.info(f'Running Task {self.__get_task_id(i)}... ')
            task.run(agent, verbose=verbose, render=render)
            total_episodes += len(task.episode_rewards)
            if verbose >= 1:
                _logger.info(f'Task {self.__get_task_id(i)} finished after '
                             f'{len(task.episode_rewards)} episodes.')
                wall_time, cpu_time = stopwatch.lap()
                _logger.info(f'Elapsed task wall time: {wall_time:.2f} sec')
                _logger.info(f'Elapsed task CPU time: {cpu_time:.2f} sec')
                _logger.info(f'Average steps per episode: {np.mean(task.step_counts):.2f}')
                _logger.info(f'Average reward per episode: {np.mean(task.episode_rewards):.2f}')
        if verbose >= 1:
            _logger.info(f'Curriculum finished after {total_episodes} episodes.')
            wall_time, cpu_time = stopwatch.stop()
            _logger.info(f'Elapsed total wall time: {wall_time:.2f} sec')
            _logger.info(f'Elapsed total CPU time: {cpu_time:.2f} sec')

    def __get_task_id(self, idx: int) -> str:
        task = self.tasks[idx]
        return str(idx + 1) if task.name is None else task.name

    @classmethod
    def load(cls, path: str) -> 'Curriculum':
        # add file extension (consistency with save() method)
        if not path.endswith('.yml'):
            path += '.curriculum.yml'
        with open(path, 'r') as file:
            curriculum_data: dict = yaml.safe_load(file)
        directory = os.path.dirname(path)
        tasks = []
        for task_id in curriculum_data['order']:
            task_data: dict = curriculum_data['tasks'][task_id]
            # tasks can be stored in two ways:
            # 1. full task data (as stored in Curriculum.save)
            # 2. path to a task config file (relative from curriculum file)
            if 'path' not in task_data.keys():
                task = LearningTask.from_dict(task_data)
            else:
                task_path_abs = os.path.abspath(
                    os.path.join(directory, task_data['path'])
                )
                task = LearningTask.load(task_path_abs)
            tasks.append(task)
        return Curriculum(tasks)

    def save(self, path: str) -> None:
        # dict preserves insertion order
        curr_data = {
            'order': list(range(len(self.tasks))),
            'tasks': {i: task.to_dict() for i, task in enumerate(self.tasks)},
        }
        # add file extension
        if not path.endswith('.yml'):
            path += '.curriculum.yml'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file:
            yaml.dump(curr_data, file)
