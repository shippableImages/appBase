# Copyright 2013 Google Inc. All Rights Reserved.

"""One-line documentation for auth module.

A detailed description of auth.
"""

import mutex
import os
import time
import urllib2

from googlecloudsdk.core import config
from googlecloudsdk.core.util import files


GOOGLE_GCE_METADATA_URI = 'http://metadata.google.internal/computeMetadata/v1'

GOOGLE_GCE_METADATA_DEFAULT_ACCOUNT_URI = (
    GOOGLE_GCE_METADATA_URI + '/instance/service-accounts/default/email')

GOOGLE_GCE_METADATA_PROJECT_URI = (
    GOOGLE_GCE_METADATA_URI + '/project/project-id')

GOOGLE_GCE_METADATA_NUMERIC_PROJECT_URI = (
    GOOGLE_GCE_METADATA_URI + '/project/numeric-project-id')

GOOGLE_GCE_METADATA_ACCOUNTS_URI = (
    GOOGLE_GCE_METADATA_URI + '/instance/service-accounts')

GOOGLE_GCE_METADATA_ACCOUNT_URI = (
    GOOGLE_GCE_METADATA_ACCOUNTS_URI + '/{account}/email')

GOOGLE_GCE_METADATA_ZONE_URI = (
    GOOGLE_GCE_METADATA_URI + '/instance/zone')

GOOGLE_GCE_METADATA_HEADERS = {'Metadata-Flavor': 'Google'}

_GCE_CACHE_MAX_AGE = 10*60  # 10 minutes


class Error(Exception):
  """Exceptions for the gce module."""


class MetadataServerException(Error):
  """Exception for when the metadata server cannot be reached."""


class CannotConnectToMetadataServerException(MetadataServerException):
  """Exception for when the metadata server cannot be reached."""


def _ReadNoProxy(uri):
  """Opens a URI without using a proxy and reads all data from it."""
  request = urllib2.Request(uri, headers=GOOGLE_GCE_METADATA_HEADERS)
  return urllib2.build_opener(urllib2.ProxyHandler({})).open(
      request, timeout=1).read()


def _ReadNoProxyWithCleanFailures(uri, http_errors_to_ignore=()):
  """Reads data from a URI with no proxy, yielding cloud-sdk exceptions."""
  try:
    return _ReadNoProxy(uri)
  except urllib2.HTTPError as e:
    if e.code in http_errors_to_ignore:
      return None
    raise MetadataServerException(e)
  except urllib2.URLError as e:
    raise CannotConnectToMetadataServerException(e)


class _GCEMetadata(object):
  """Class for fetching GCE metadata.

  Attributes:
    connected: bool, True if the metadata server is available.

  """

  def __init__(self):
    if _IsGCECached():
      self.connected = _IsOnGCEViaCache()
      return

    try:
      numeric_project_id = _ReadNoProxy(
          GOOGLE_GCE_METADATA_NUMERIC_PROJECT_URI)
      self.connected = numeric_project_id.isdigit()
    except urllib2.HTTPError:
      self.connected = False
    except urllib2.URLError:
      self.connected = False

    _CacheIsOnGCE(self.connected)

  def DefaultAccount(self):
    """Get the default service account for the host GCE instance.

    Fetches GOOGLE_GCE_METADATA_DEFAULT_ACCOUNT_URI and returns its contents.

    Raises:
      CannotConnectToMetadataServerException: If the metadata server
          cannot be reached.
      MetadataServerException: If there is a problem communicating with the
          metadata server.

    Returns:
      str, The email address for the default service account. None if not on a
          GCE VM, or if there are no service accounts associated with this VM.
    """

    if not self.connected:
      return None

    return _ReadNoProxyWithCleanFailures(
        GOOGLE_GCE_METADATA_DEFAULT_ACCOUNT_URI,
        http_errors_to_ignore=(404,))

  def Project(self):
    """Get the project that owns the current GCE instance.

    Fetches GOOGLE_GCE_METADATA_PROJECT_URI and returns its contents.

    Raises:
      CannotConnectToMetadataServerException: If the metadata server
          cannot be reached.
      MetadataServerException: If there is a problem communicating with the
          metadata server.

    Returns:
      str, The email address for the default service account. None if not on a
          GCE VM.
    """

    if not self.connected:
      return None

    return _ReadNoProxyWithCleanFailures(GOOGLE_GCE_METADATA_PROJECT_URI)

  def Accounts(self):
    """Get the list of service accounts available from the metadata server.

    Returns:
      [str], The list of accounts. [] if not on a GCE VM.

    Raises:
      CannotConnectToMetadataServerException: If no metadata server is present.
      MetadataServerException: If there is a problem communicating with the
          metadata server.
    """

    if not self.connected:
      return []

    accounts_listing = _ReadNoProxyWithCleanFailures(
        GOOGLE_GCE_METADATA_ACCOUNTS_URI + '/')
    accounts_lines = accounts_listing.split()
    accounts = []
    for account_line in accounts_lines:
      account = account_line.strip('/')
      if account == 'default':
        continue
      accounts.append(account)
    return accounts

  def Zone(self):
    """Get the name of the zone containing the current GCE instance.

    Fetches GOOGLE_GCE_METADATA_ZONE_URI, formats it, and returns its contents.

    Raises:
      CannotConnectToMetadataServerException: If the metadata server
          cannot be reached.
      MetadataServerException: If there is a problem communicating with the
          metadata server.

    Returns:
      str, The short name (e.g., us-central1-f) of the zone containing the
          current instance.
      None if not on a GCE VM.
    """

    if not self.connected:
      return None

    # zone_path will be formatted as, for example,
    # projects/123456789123/zones/us-central1-f
    # and we want to return only the last component.
    zone_path = _ReadNoProxyWithCleanFailures(GOOGLE_GCE_METADATA_ZONE_URI)
    return zone_path.split('/')[-1]

  def Region(self):
    """Get the name of the region containing the current GCE instance.

    Fetches GOOGLE_GCE_METADATA_ZONE_URI, extracts the region associated
    with the zone, and returns it.  Extraction is based property that
    zone names have form <region>-<zone> (see https://cloud.google.com/
    compute/docs/zones) and an assumption that <zone> contains no hyphens.

    Raises:
      CannotConnectToMetadataServerException: If the metadata server
          cannot be reached.
      MetadataServerException: If there is a problem communicating with the
          metadata server.

    Returns:
      str, The short name (e.g., us-central1) of the region containing the
          current instance.
      None if not on a GCE VM.
    """

    if not self.connected:
      return None

    # Zone will be formatted as (e.g.) us-central1-a, and we want to return
    # everything ahead of the lasy hyphen.
    zone = self.Zone()
    return '/'.join(zone.split('/')[:-1])


_metadata = None
_metadata_lock = mutex.mutex()


def Metadata():
  """Get a singleton that fetches GCE metadata.

  Returns:
    _GCEMetadata, An object used to collect information from the GCE metadata
    server.
  """
  def _CreateMetadata(unused_none):
    global _metadata
    if not _metadata:
      _metadata = _GCEMetadata()
  _metadata_lock.lock(function=_CreateMetadata, argument=None)
  _metadata_lock.unlock()
  return _metadata


def _CacheIsOnGCE(on_gce):
  with files.OpenForWritingPrivate(
      config.Paths().GCECachePath()) as gcecache_file:
    gcecache_file.write(str(on_gce))


def _IsGCECached():
  gce_cache_path = config.Paths().GCECachePath()
  if not os.path.exists(gce_cache_path):
    return False
  cache_mod = os.stat(gce_cache_path).st_mtime
  cache_age = time.time() - cache_mod
  if cache_age > _GCE_CACHE_MAX_AGE:
    return False
  return True


def _IsOnGCEViaCache():
  gce_cache_path = config.Paths().GCECachePath()
  if os.path.exists(gce_cache_path):
    with open(gce_cache_path) as gcecache_file:
      return gcecache_file.read() == str(True)
  return False
