"""
Custom exception module
Defines custom exception classes used by the scheduler
"""


class SchedulerException(Exception):
    """Scheduler base exception class"""
    pass


class ConfigurationError(SchedulerException):
    """Configuration error exception"""
    pass


class F5ApiError(SchedulerException):
    """F5 API related exception"""
    pass


class MetricsCollectionError(SchedulerException):
    """Metrics collection exception"""
    pass


class ScoreCalculationError(SchedulerException):
    """Score calculation exception"""
    pass


class SchedulingError(SchedulerException):
    """Scheduling exception"""
    pass


class TokenAuthenticationError(F5ApiError):
    """Token authentication exception"""
    pass


class InvalidRequestError(SchedulerException):
    """Invalid request exception"""
    pass 