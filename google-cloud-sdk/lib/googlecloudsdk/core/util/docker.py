# Copyright 2014 Google Inc. All Rights Reserved.

"""Utility library for configuring access to the Google Container Registry.

Sets docker up to authenticate with the Google Container Registry using the
active gcloud credential.
"""

import base64
import errno
import json
import os
import subprocess
import sys

from googlecloudsdk.core import exceptions
from googlecloudsdk.core.credentials import store
from googlecloudsdk.core.util import files

_USERNAME = '_token'


# Other tools like the python docker library (used by gcloud app)
# also rely on .dockercfg (in addition to the docker CLI client)
# NOTE: Lazy for manipulation of HOME / mocking.
def GetDockerConfig():
  """Retrieve the path to '.dockercfg' in a docker-py compatible fashion.

  Returns:
    The path on the host machine to '.dockercfg', as expected by the docker
    client.
  """
  # TODO(user): While os.path.expanduser('~') is more portable, here we
  # very intentionally match the paired logic from docker/docker-py, which
  # uses the HOME variable directly.
  return os.path.join(os.environ.get('HOME', '.'), '.dockercfg')


def ReadDockerConfig():
  """Retrieve the contents of '.dockercfg'.

  NOTE: This is public only to facilitate testing.

  Returns:
    The contents of '.dockercfg'.
  """
  with open(GetDockerConfig(), 'r') as reader:
    return reader.read()


def WriteDockerConfig(contents):
  """Write the contents to '.dockercfg'.

  This is public only to facilitate testing.

  Args:
    contents: The body to write to '.dockercfg'.
  """
  with files.OpenForWritingPrivate(GetDockerConfig()) as writer:
    writer.write(contents)


def UpdateDockerCredentials(server):
  """Updates the docker config to have fresh credentials.

  This reads the current contents of '.dockercfg', adds extends it with
  a fresh entry for the provided 'server', based on the active gcloud
  credential.  If a credential exists for 'server' this replaces it.

  Args:
    server: The hostname of the registry for which we're freshening
       the credential.

  Raises:
    store.Error: There was an error loading the credentials.
  """
  # Loading credentials will ensure that we're logged in.
  # And prompt/abort to 'run gcloud auth login' otherwise.
  cred = store.Load()

  # Ensure our credential has a valid access token,
  # which has the full duration available.
  store.Refresh(cred)
  if not cred.access_token:
    raise exceptions.Error('No access token could be obtained '
                           'from the current credentials.')

  # Update the docker configuration file passing the access token
  # as a password, and a benign value as the username.
  _UpdateDockerConfig(server, _USERNAME, cred.access_token)


def _UpdateDockerConfig(server, username, access_token):
  """Register the username and token for the given server in '.dockercfg'."""

  # NOTE: using "docker login" doesn't work as they're quite strict on what
  # is allowed in username/password.
  try:
    dockercfg_contents = json.loads(ReadDockerConfig())
  except IOError:
    # If the file doesn't exist, start with an empty map.
    dockercfg_contents = {}

  # Add the entry for our server.
  auth = base64.b64encode(username + ':' + access_token)

  # Clear out any unqualified stale entry for this server
  if server in dockercfg_contents:
    del dockercfg_contents[server]

  scheme = 'https://'
  dockercfg_contents[scheme + server] = {'auth': auth,
                                         'email': 'not@val.id'}

  # TODO(user): atomic replace?
  # Be nice and pretty-print.
  WriteDockerConfig(json.dumps(dockercfg_contents, indent=2))


# Modeled after EnsureGit in workspaces.py
def EnsureDocker(func):
  """Wraps a function that uses subprocess to invoke docker.

  Rewrites OS Exceptions when not installed.

  Args:
    func: A function that uses subprocess to invoke docker.

  Returns:
    The decorated function.

  Raises:
    Error: Docker cannot be run.
  """
  def DockerFunc(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except OSError as e:
      if e.errno == errno.ENOENT:
        raise exceptions.Error('Docker is not installed.')
      else:
        raise
  return DockerFunc


@EnsureDocker
def Execute(args):
  """Wraps an invocation of the docker client with the specified CLI arguments.

  Args:
    args: The list of command-line arguments to docker.

  Raises:
    exceptions.Error: The docker command returned a non-zero exit code.
  """
  result = subprocess.call(['docker'] + args,
                           stdin=sys.stdin,
                           stdout=sys.stdout,
                           stderr=sys.stderr)
  if result != 0:
    raise exceptions.Error("""\
A Docker command did not run successfully.
Tried to run: '{command}'
Exit code: {exit_code}
""".format(exit_code=result, command=' '.join(['docker'] + args)))
