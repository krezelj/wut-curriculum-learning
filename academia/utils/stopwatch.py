from typing import Callable, Optional
import time

import numpy as np


class Stopwatch:
    """A utility class for measuring and storing consecutive CPU/wall times.
    All times are stored in seconds."""

    def __init__(self, start=True):
        """
        Args:
            start: whether or not to start a stopwatch immidiately after initialising it.
        """
        self.__wall_stopwatch = _GenericStopwatch(timestamp_func=time.perf_counter, start=start)
        self.__cpu_stopwatch = _GenericStopwatch(timestamp_func=time.process_time, start=start)

    @property
    def is_running(self) -> bool:
        return self.__wall_stopwatch.is_running

    def start(self) -> None:
        """Starts or restarts the stopwatch"""
        self.__wall_stopwatch.start()
        self.__cpu_stopwatch.start()

    def peek_time(self) -> tuple[float, float]:
        """
        Returns:
            Current time since the start.
        """
        return self.__wall_stopwatch.peek_time(), self.__cpu_stopwatch.peek_time()

    def lap(self) -> tuple[float, float]:
        """
        Returns:
             Wall and CPU lap times.
        """
        return self.__wall_stopwatch.lap(), self.__cpu_stopwatch.lap()

    def peek_lap_time(self) -> tuple[float, float]:
        """
        Returns:
            Current lap time.
        """
        return self.__wall_stopwatch.peek_lap_time(), self.__cpu_stopwatch.peek_lap_time()

    def stop(self, lap=False) -> tuple[float, float]:
        """
        Args:
            lap: whether or not end and save the final lap.

        Returns:
             Wall and CPU total times.
        """
        wall_total = self.__wall_stopwatch.stop(lap=lap)
        cpu_total = self.__cpu_stopwatch.stop(lap=lap)
        return wall_total, cpu_total

    @property
    def wall_lap_times(self) -> list[float]:
        return self.__wall_stopwatch.lap_times

    @property
    def cpu_lap_times(self) -> list[float]:
        return self.__cpu_stopwatch.lap_times


class _GenericStopwatch:

    def __init__(self, timestamp_func: Callable[[], float], start=True):
        """
        Args:
            start: whether or not to start a stopwatch immidiately after initialising it.
        """
        self.__timestamp_func = timestamp_func
        self.lap_times: list[float] = []
        self.__lap_start: Optional[float] = None
        if start:
            self.start()

    @property
    def is_running(self) -> bool:
        return self.__lap_start is not None

    def start(self) -> None:
        """Starts or restarts the stopwatch"""
        if self.is_running:
            self.stop()
        self.lap_times.clear()
        self.__lap_start = self.__timestamp_func()

    def peek_time(self) -> float:
        """
        Returns:
            Current time since the start.

        Raises:
            RuntimeError: if stopwatch is not running
        """
        if not self.is_running:
            raise RuntimeError('Cannot peek the current time - the stopwatch is not running')
        return self.peek_lap_time() + np.sum(self.lap_times)

    def lap(self) -> float:
        """
        Returns:
             Lap time.

        Raises:
            RuntimeError: if stopwatch is not running
        """
        if not self.is_running:
            raise RuntimeError('Cannot lap - the stopwatch is not running')
        curr_time = self.__timestamp_func()
        lap_time = curr_time - self.__lap_start
        self.lap_times.append(lap_time)
        self.__lap_start = curr_time
        return lap_time

    def peek_lap_time(self) -> float:
        """
        Returns:
            Current lap time.

        Raises:
            RuntimeError: if stopwatch is not running
        """
        if not self.is_running:
            raise RuntimeError('Cannot peek the current time - the stopwatch is not running')
        curr_time = self.__timestamp_func()
        return curr_time - self.__lap_start

    def stop(self, lap=False) -> float:
        """
        Args:
            lap: whether or not end and save the final lap.

        Returns:
             Total time.

        Raises:
            RuntimeError: if stopwatch is not running
        """
        if not self.is_running:
            raise RuntimeError('Cannot stop - the stopwatch is not running')
        if lap:
            self.lap()
            total_time = np.sum(self.lap_times)
        else:
            curr_time = self.__timestamp_func()
            total_time = np.sum(self.lap_times) + (curr_time - self.__lap_start)
        self.__lap_start = None
        return total_time
