# Copyright 2014 Google Inc. All Rights Reserved.

"""Utilities for accessing local pakage resources."""

import pkgutil


def _GetPackageName(module_name):
  """Returns package name for given module name."""
  last_dot_idx = module_name.rfind('.')
  if last_dot_idx > 0:
    return module_name[:last_dot_idx]
  return ''


def GetResource(module_name, resource_name):
  """Get a resource as a string for given resource in same package."""
  return pkgutil.get_data(_GetPackageName(module_name), resource_name)
