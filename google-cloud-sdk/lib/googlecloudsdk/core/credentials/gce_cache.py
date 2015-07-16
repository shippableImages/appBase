# Copyright 2013 Google Inc. All Rights Reserved.

"""Caching logic for checking if we're on GCE."""

import os
from threading import Lock
import time
import urllib2

from googlecloudsdk.core import config
from googlecloudsdk.core.credentials import gce_read
from googlecloudsdk.core.util import files


_GCE_CACHE_MAX_AGE = 10*60  # 10 minutes


class _OnGCECache(object):
  """Logic to check if we're on GCE and cache the result to file or memory."""

  def __init__(self):
    self.connected = None
    self.mtime = None
    self.file_lock = Lock()

  def GetOnGCE(self, check_age=True):
    if self.connected is None or self.mtime is None:
      self._UpdateMemory()
    if check_age:
      if time.time() - self.mtime > _GCE_CACHE_MAX_AGE:
        self._UpdateFileCache()
        self._UpdateMemory()
    return self.connected

  def _UpdateMemory(self):
    """Read from file and store in memory."""
    gce_cache_path = config.Paths().GCECachePath()
    if not os.path.exists(gce_cache_path):
      self._UpdateFileCache()
    with self.file_lock:
      self.mtime = os.stat(gce_cache_path).st_mtime
      with open(gce_cache_path) as gcecache_file:
        self.connected = gcecache_file.read() == str(True)

  def _UpdateFileCache(self):
    """Check server if connected, write the result to file."""
    gce_cache_path = config.Paths().GCECachePath()
    on_gce = self._CheckServer()
    with self.file_lock:
      with files.OpenForWritingPrivate(gce_cache_path) as gcecache_file:
        gcecache_file.write(str(on_gce))

  def _CheckServer(self):
    try:
      numeric_project_id = gce_read.ReadNoProxy(
          gce_read.GOOGLE_GCE_METADATA_NUMERIC_PROJECT_URI)
      return numeric_project_id.isdigit()
    except urllib2.HTTPError:
      return False
    except urllib2.URLError:
      return False

# Since a module is initialized only once, this is effective a singleton
_SINGLETON_ON_GCE_CACHE = _OnGCECache()


def GetOnGCE(check_age=True):
  """Helper function to abstract the caching logic of if we're on GCE."""
  return _SINGLETON_ON_GCE_CACHE.GetOnGCE(check_age)
