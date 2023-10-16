import os

import yaml

from . import Task
from academia.utils import SavableLoadable


# TODO Add more statistics about agent training process (e.g. time to train)
# TODO Possibly add ability to form the curriculum as a dynamic directed graph
# (many parallel dependencies, adding new tasks automatically etc. probably very advanced)

class Curriculum(SavableLoadable):

    __slots__ = ['tasks']

    def __init__(self, tasks: list[Task]) -> None:
        self.tasks = tasks

    def run(self, agent, verbose=0):
        total_episodes = 0
        for i, task in enumerate(self.tasks):
            if verbose > 0:
                print(f"Running Task: {i + 1 if task.name is None else task.name}... ", end="")
            task.run()
            total_episodes += len(task.episode_rewards)
            if verbose > 0:
                print(f"finished after {len(task.episode_rewards)} episodes.")
        if verbose > 0:
            print(f"Curriculum finished after {total_episodes} episodes.")

    @classmethod
    def load(cls, path: str) -> 'Curriculum':
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
                task = Task.from_dict(task_data)
            else:
                task_path_abs = os.path.abspath(
                    os.path.join(directory, task_data['path'])
                )
                task = Task.load(task_path_abs)
            tasks.append(task)
        return Curriculum(tasks)

    def save(self, path: str) -> None:
        # dict preserves insertion order
        curr_data = {
            'order': list(range(len(self.tasks))),
            'tasks': {i: task.to_dict() for i, task in enumerate(self.tasks)},
        }
        # add file extension
        if not path.endswith('.yml') and not path.endswith('.curriculum'):
            path += '.curriculum.yml'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file:
            yaml.dump(curr_data, file)
