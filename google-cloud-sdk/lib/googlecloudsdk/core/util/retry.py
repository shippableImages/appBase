# Copyright 2015 Google Inc. All Rights Reserved.

"""Implementation of retrying logic."""

import collections
import functools
import itertools
import random
import sys
import time


_DEFAULT_JITTER_MS = 1000


# TODO(user): replace retry logic elsewhere
# (appengine/lib, compute, bigquery ...) with this implementation.
class RetryException(Exception):
  """Raised to stop retrials on failure."""

  def __init__(self, message, last_result, last_retrial,
               time_passed_ms, time_to_wait_ms):
    self.message = message
    self.last_result = last_result
    self.last_retrial = last_retrial
    self.time_passed_ms = time_passed_ms
    self.time_to_wait_ms = time_to_wait_ms
    super(RetryException, self).__init__(message)

  def __str__(self):
    return ('last_result={last_result}, last_retrial={last_retrial}, '
            'time_passed_ms={time_passed_ms},'
            'time_to_wait={time_to_wait_ms}'.format(
                last_result=self.last_result,
                last_retrial=self.last_retrial,
                time_passed_ms=self.time_passed_ms,
                time_to_wait_ms=self.time_to_wait_ms))


class WaitException(RetryException):
  """Raised when timeout was reached."""


class MaxRetrialsException(RetryException):
  """Raised when too many retrials reached."""


class Retryer(object):
  """Retries a function based on specified retry strategy."""

  def __init__(self, max_retrials=None, max_wait_ms=None,
               exponential_sleep_multiplier=None, jitter_ms=_DEFAULT_JITTER_MS,
               status_update_func=None, wait_ceiling_ms=None):
    """Initializer for Retryer.

    Args:
      max_retrials: int, max number of retrials before raising RetryException.
      max_wait_ms: int, number of ms to wait before raising
      exponential_sleep_multiplier: float, The exponential factor to use on
          subsequent retries.
      jitter_ms: int, random [0, jitter_ms] additional value to wait.
      status_update_func: func(retrial, time_passed_ms, time_to_wait_ms, result)
          called right after each trail.
      wait_ceiling_ms: int, maximum wait time between retries, regardless of
          modifiers added like exponential multiplier or jitter.
    """

    self._max_retrials = max_retrials
    self._max_wait_ms = max_wait_ms
    self._exponential_sleep_multiplier = exponential_sleep_multiplier
    self._jitter_ms = jitter_ms
    self._status_update_func = status_update_func
    self._wait_ceiling_ms = wait_ceiling_ms

  def _RaiseIfStop(self, result, retrial, time_passed_ms, time_to_wait_ms):
    if self._max_wait_ms is not None:
      if time_passed_ms + time_to_wait_ms > self._max_wait_ms:
        raise WaitException('Timeout', result, retrial, time_passed_ms,
                            time_to_wait_ms)
    if self._max_retrials is not None and self._max_retrials <= retrial:
      raise MaxRetrialsException('Reached', result, retrial, time_passed_ms,
                                 time_to_wait_ms)

  def _GetTimeToWait(self, last_retrial, sleep_ms):
    """Get time to wait after applying modifyers.

    Apply the exponential sleep multiplyer, jitter and ceiling limiting to the
    base sleep time.

    Args:
      last_retrial: int, which retry attempt we just tried. First try this is 0.
      sleep_ms: int, how long to wait between the current trials.

    Returns:
      int, ms to wait before trying next attempt with all waiting logic applied.
    """
    wait_time_ms = sleep_ms
    if wait_time_ms:
      if self._exponential_sleep_multiplier:
        wait_time_ms *= self._exponential_sleep_multiplier ** last_retrial
      if self._jitter_ms:
        wait_time_ms += random.random() * self._jitter_ms
      if self._wait_ceiling_ms:
        wait_time_ms = min(wait_time_ms, self._wait_ceiling_ms)
      return wait_time_ms
    return 0

  def RetryOnException(self, func, args=None, kwargs=None,
                       should_retry_if=None, sleep_ms=None):
    """Retries the function if an exception occurs.

    Args:
      func: The function to call and retry.
      args: a sequence of positional arguments to be passed to func.
      kwargs: a dictionary of positional arguments to be passed to func.
      should_retry_if: func(exc_info)
      sleep_ms: int or iterable for how long to wait between trials.

    Returns:
      Whatever the function returns.

    Raises:
      RetryException, WaitException: if function is retries too many times,
        or time limit is reached.
    """

    args = args if args is not None else ()
    kwargs = kwargs if kwargs is not None else {}

    def TryFunc():
      try:
        return func(*args, **kwargs), None
      except:  # pylint: disable=bare-except
        return None, sys.exc_info()

    if should_retry_if is None:
      should_retry = lambda x: x[1] is not None
    else:
      should_retry = lambda x: x[1] is not None and should_retry_if(*x[1])

    return self.RetryOnResult(TryFunc, [], {}, should_retry, sleep_ms)[0]

  def RetryOnResult(self, func, args=None, kwargs=None,
                    should_retry_if=None, sleep_ms=None):
    """Retries the function if the given condition is satisfied.

    Args:
      func: The function to call and retry.
      args: a sequence of arguments to be passed to func.
      kwargs: a dictionary of positional arguments to be passed to func.
      should_retry_if: result or func(result) should retry on.
      sleep_ms: int or iterable, for how long to wait between trials.

    Returns:
      Whatever the function returns.

    Raises:
      RetryException, WaitException: if function is retries too many times,
        or time limit is reached.
    """
    args = args if args is not None else ()
    kwargs = kwargs if kwargs is not None else {}

    start_time_ms = int(time.time() * 1000)
    retrial = 0
    if callable(should_retry_if):
      should_retry = should_retry_if
    else:
      should_retry = lambda x: x == should_retry_if

    if isinstance(sleep_ms, collections.Iterable):
      sleep_gen = iter(sleep_ms)
    else:
      sleep_gen = itertools.repeat(sleep_ms)

    while True:
      result = func(*args, **kwargs)
      if not should_retry(result):
        return result
      time_passed_ms = int(time.time() * 1000) - start_time_ms
      try:
        time_to_wait_ms = self._GetTimeToWait(retrial, sleep_gen.next())
      except StopIteration:
        raise MaxRetrialsException('Sleep iteration stop',
                                   result, retrial, time_passed_ms, 0)
      if self._status_update_func:
        self._status_update_func(retrial,
                                 time_passed_ms,
                                 time_to_wait_ms,
                                 result)
      self._RaiseIfStop(result, retrial, time_passed_ms, time_to_wait_ms)
      time.sleep(time_to_wait_ms / 1000.0)
      retrial += 1


def RetryOnException(f=None, max_retrials=None, max_wait_ms=None,
                     sleep_ms=None, exponential_sleep_multiplier=None,
                     jitter_ms=_DEFAULT_JITTER_MS,
                     status_update_func=None,
                     should_retry_if=None):
  """A decorator to retry on exceptions.

  Args:
    f: a function to run possibly multiple times
    max_retrials: int, max number of retrials before raising RetryException.
    max_wait_ms: int, number of ms to wait before raising
    sleep_ms: int or iterable, for how long to wait between trials.
    exponential_sleep_multiplier: float, The exponential factor to use on
        subsequent retries.
    jitter_ms: int, random [0, jitter_ms] additional value to wait.
    status_update_func: func(retrial, time_passed_ms, time_to_wait_ms, result)
        called right after each trail.
    should_retry_if: func(exc_info)

  Returns:
    A version of f that is executed potentially multiple times and that
    yields the first returned value or the last exception raised.
  """

  if f is None:
    # Returns a decorator---based on retry Retry with max_retrials,
    # max_wait_ms, sleep_ms, etc. fixed.
    return functools.partial(
        RetryOnException,
        exponential_sleep_multiplier=exponential_sleep_multiplier,
        jitter_ms=jitter_ms,
        max_retrials=max_retrials,
        max_wait_ms=max_wait_ms,
        should_retry_if=should_retry_if,
        sleep_ms=sleep_ms,
        status_update_func=status_update_func)

  @functools.wraps(f)
  def DecoratedFunction(*args, **kwargs):
    retryer = Retryer(
        max_retrials=max_retrials,
        max_wait_ms=max_wait_ms,
        exponential_sleep_multiplier=exponential_sleep_multiplier,
        jitter_ms=jitter_ms,
        status_update_func=status_update_func)
    try:
      return retryer.RetryOnException(f, args=args, kwargs=kwargs,
                                      should_retry_if=should_retry_if,
                                      sleep_ms=sleep_ms)
    except MaxRetrialsException as mre:
      to_reraise = mre.last_result[1]
      raise to_reraise[0], to_reraise[1], to_reraise[2]

  return DecoratedFunction
