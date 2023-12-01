import argparse
import sys
import json
import os
import logging
from typing import Literal, Optional

import numpy as np

sys.path.append('../..')

from academia.environments import LunarLander
from academia.agents import DQNAgent, PPOAgent
from academia.curriculum import LearningTask, Curriculum
from academia.utils.models import lunar_lander
from academia.utils import Stopwatch


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)-19s] [%(levelname)-8s] %(name)s: %(message)s ',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='experiment_3.log',
)

_logger = logging.getLogger('academia.curriculum')


def load_meta():
    if not os.path.exists('meta.json'):
        meta = {
            'n_runs': 10,
            'ppo': {
                'curr_runs': 0,
                'curr_steps_sum': 0,
                'nocurr_runs': 0
            },
            'dqn': {
                'curr_runs': 0,
                'curr_steps_sum': 0,
                'nocurr_runs': 0
            }
        }
    else:
        with open('meta.json', 'r') as f:
            meta = json.load(f)
    return meta


def save_meta(meta: dict):
    with open('meta.json', 'w') as f:
        json.dump(meta, f, indent=4)


def get_task(
        difficulty: int = 3,
        min_evaluation_score: int = 250,
        max_steps: int = np.inf,
        greedy_evaluation: bool = True,
        save_path: Optional[str] = None):
    task = LearningTask(
        LunarLander,
        env_args={'difficulty': difficulty, 'random_state': 42, 'append_step_count': True},
        stop_conditions={
            'min_evaluation_score': min_evaluation_score,
            'max_steps': max_steps},
        evaluation_count=25,
        greedy_evaluation=greedy_evaluation,
        exploration_reset_value=0.3,
        stats_save_path=save_path,
        agent_save_path=save_path
    )
    return task


def get_curriculum(greedy_evaluation: bool, output_dir: str):
    tasks = [
        get_task(0, 250, greedy_evaluation=greedy_evaluation),
        get_task(1, 250, greedy_evaluation=greedy_evaluation),
        get_task(2, 250, greedy_evaluation=greedy_evaluation),
        get_task(3, 250, greedy_evaluation=greedy_evaluation),
    ]
    curriculum = Curriculum(
        tasks,
        output_dir=output_dir
    )
    return curriculum


def get_runnable(
        runnable_type: Literal['curr', 'nocurr'], 
        agent_type: Literal['ppo', 'dqn'], 
        i: int,
        max_steps: int):
    if runnable_type == 'curr':
        return get_curriculum(
            greedy_evaluation=True,
            output_dir=f'./outputs/{agent_type}/curriculum_{i}'
        )
    elif runnable_type == 'nocurr':
        return get_task(
            save_path=f'./outputs/{agent_type}/nocurriculum_{i}/nocurr',
            max_steps=max_steps,
        )
    raise ValueError(f"Invalid runnable type: {runnable_type}")


def get_agent(agent_type: Literal['dqn', 'ppo'], random_state: int):
    if agent_type == 'dqn':
        return DQNAgent(
            lunar_lander.MLPStepDQN,
            n_actions=4,
            epsilon_decay=0.9995,
            device='cpu',
            random_state=random_state
        )
    if agent_type == 'ppo':
        return PPOAgent(
            lunar_lander.MLPStepActor,
            lunar_lander.MLPStepCritic,
            n_actions=4,
            n_episodes=10,
            device='cpu',
            random_state=random_state
        )


def determine_next_run(
        meta: dict, 
        force_agent_type: Optional[Literal['dqn', 'ppo']] = None,
        allow_curr: bool = True,
        allow_nocurr: bool = True):
    n_runs = meta['n_runs']
    can_use_ppo = force_agent_type is None or force_agent_type == 'ppo'
    can_use_dqn = force_agent_type is None or force_agent_type == 'dqn'

    # ppo curr
    if can_use_ppo and \
            allow_curr and \
            meta['ppo']['curr_runs'] < n_runs:
        return (
            'ppo', 
            'curr', 
            meta['ppo']['curr_runs'],
            meta['ppo']['curr_runs'] + 0 * n_runs)
    
    # ppo nocurr
    elif can_use_ppo and \
            allow_nocurr and \
            meta['ppo']['curr_runs'] == n_runs and \
            meta['ppo']['nocurr_runs'] < n_runs:
        return (
            'ppo', 
            'nocurr', 
            meta['ppo']['nocurr_runs'],
            meta['ppo']['nocurr_runs'] + 1 * n_runs)
    
    # dqn curr
    if can_use_dqn and \
            allow_curr and \
            meta['dqn']['curr_runs'] < n_runs:
        return (
            'dqn', 
            'curr', 
            meta['dqn']['curr_runs'],
            meta['dqn']['curr_runs'] + 2 * n_runs)
    
    # dqn nocurr
    elif can_use_dqn and \
            allow_nocurr and \
            meta['dqn']['curr_runs'] == n_runs and \
            meta['dqn']['nocurr_runs'] < n_runs:
        return (
            'dqn', 
            'nocurr', 
            meta['dqn']['nocurr_runs'],
            meta['dqn']['nocurr_runs'] + 3 * n_runs)
    return (None, None, None, None)
    

def run_experiment(
        n_runs: int = 1_000_000_000, 
        wall_time: float = 1_000_000_000,
        force_agent_type: Optional[Literal['ppo', 'dqn']] = None,
        allow_curr: bool = True,
        allow_nocurr: bool = True,
        ):
    
    meta = load_meta()
    runs = 0
    sw = Stopwatch()
    while True:
        runs += 1
        if runs > n_runs:
            _logger.info("Reached runs limit. Stopping experiment.")
            break
        if sw.peek_time()[0] >= wall_time:
            _logger.info("Reached time limit. Stopping experiment.")
            break

        agent_type, runnable_type, i, random_state = determine_next_run(
            meta, force_agent_type, allow_curr, allow_nocurr)
        if agent_type is None:
            _logger.info("No allowed configurations left. Stopping experiment.")
            break

        agent = get_agent(agent_type, random_state)

        if runnable_type == 'nocurr':
            max_steps = 3 * meta[agent_type]['curr_steps_sum'] / meta['n_runs']
        else:
            max_steps = np.inf

        runnable = get_runnable(runnable_type, agent_type, i, max_steps=max_steps)
        runnable.save(f'./configs/{agent_type}_{runnable_type}_{i}')

        try:
            _logger.info(f"Starting {runnable_type} for {agent_type} (run {i+1})")
            runnable.run(agent, verbose=2)
            _logger.info(f"Finished {runnable_type} for {agent_type} (run {i+1})")
        except KeyboardInterrupt:
            save_meta(meta)

        meta[agent_type][f'{runnable_type}_runs'] += 1
        if runnable_type == 'curr':
            runnable: Curriculum
            steps_this_curriculum = 0
            for task_stats in runnable.stats.values():
                steps_this_curriculum += np.sum(task_stats.step_counts)
            meta[agent_type]['curr_steps_sum'] += steps_this_curriculum

    save_meta(meta)


def parse_options(*args):
    _argparser = argparse.ArgumentParser()
    _argparser.add_argument('-t', '--time', action='store', default=1_000_000_000,
                            help='Maximum wall time')
    _argparser.add_argument('-r', '--runs', action='store', default=1_000_000_000,
                            help='Maximum runs')
    _argparser.add_argument('-a', '--agent', action='store',
                            help='Agent type ("dqn"/"ppo")')
    _argparser.add_argument('-dc', '--discurriculum', action='store_false',
                            help='Disallow curriculum runs')
    _argparser.add_argument('-dn', '--disnocurriculum', action='store_false',
                            help='Disallow nocurriculum runs')
    args = _argparser.parse_args()
    return {
        'force_agent_type': args.agent,
        'wall_time': float(args.time),
        'n_runs': int(args.runs),
        'allow_curr': args.discurriculum,
        'allow_nocurr': args.disnocurriculum
    }
        

def main():
    kwargs = parse_options(*sys.argv[1:])
    run_experiment(**kwargs)
    

if __name__ == '__main__':
    main()

