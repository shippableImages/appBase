# Copyright 2015 Google Inc. All Rights Reserved.

"""Utilities for configuring platform specific installation."""

import os
import re
import shutil

from googlecloudsdk.core.credentials import gce as c_gce
from googlecloudsdk.core.util import console_io
from googlecloudsdk.core.util import platforms

# pylint:disable=superfluous-parens


# pylint:disable=unused-argument
def _UpdatePathForWindows(bin_path):
  """Update the Windows system path to include bin_path.

  Args:
    bin_path: str, The absolute path to the directory that will contain
        Cloud SDK binaries.
  """

  # pylint:disable=g-import-not-at-top, we want to only attempt these imports
  # on windows.
  try:
    import win32con
    import win32gui
    try:
      # Python 3
      import winreg
    except ImportError:
      # Python 2
      import _winreg as winreg
  except ImportError:
    print("""\
The installer is unable to automatically update your system PATH. Please add
  {path}
to your system PATH to enable easy use of the Cloud SDK Command Line Tools.
""".format(path=bin_path))
    return

  def GetEnv(name):
    root = winreg.HKEY_CURRENT_USER
    subkey = 'Environment'
    key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ)
    try:
      value, _ = winreg.QueryValueEx(key, name)
    # pylint:disable=undefined-variable, This variable is defined in windows.
    except WindowsError:
      return ''
    return value

  def SetEnv(name, value):
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0,
                         winreg.KEY_ALL_ACCESS)
    winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
    winreg.CloseKey(key)
    win32gui.SendMessage(
        win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 'Environment')
    return value

  def Remove(paths, value):
    while value in paths:
      paths.remove(value)

  def PrependEnv(name, values):
    paths = GetEnv(name).split(';')
    for value in values:
      if value in paths:
        Remove(paths, value)
      paths.insert(0, value)
    SetEnv(name, ';'.join(paths))

  PrependEnv('Path', [bin_path])

  print("""\
The following directory has been added to your PATH.
  {bin_path}

Create a new command shell for the changes to take effect.
""".format(bin_path=bin_path))


def UpdateRC(bash_completion, path_update, rc_path, bin_path, sdk_root):
  """Update the system path to include bin_path.

  Args:
    bash_completion: bool, Whether or not to do bash completion. If None, ask.
    path_update: bool, Whether or not to do bash completion. If None, ask.
    rc_path: str, The path to the rc file to update. If None, ask.
    bin_path: str, The absolute path to the directory that will contain
        Cloud SDK binaries.
    sdk_root: str, The path to the Cloud SDK root.
  """

  host_os = platforms.OperatingSystem.Current()
  if host_os == platforms.OperatingSystem.WINDOWS:
    if path_update is None:
      path_update = console_io.PromptContinue(
          prompt_string='Update %PATH% to include Cloud SDK binaries?')
    if path_update:
      _UpdatePathForWindows(bin_path)
    return

  completion_rc_path = os.path.join(sdk_root, 'completion.bash.inc')
  path_rc_path = os.path.join(sdk_root, 'path.bash.inc')

  if bash_completion is None:
    if path_update is None:  # Ask only one question if both were not set.
      path_update = console_io.PromptContinue(
          prompt_string=('\nModify profile to update your $PATH '
                         'and enable bash completion?'))
      bash_completion = path_update
    else:
      bash_completion = console_io.PromptContinue(
          prompt_string=('\nModify profile to enable bash completion?'))
  elif path_update is None:
    path_update = console_io.PromptContinue(
        prompt_string=('\nModify profile to update your $PATH?'))

  if not bash_completion:
    print("""\
Source [{completion_rc_path}]
in your profile to enable bash completion for gcloud.
""".format(completion_rc_path=completion_rc_path))

  if not path_update:
    print("""\
Source [{path_rc_path}]
in your profile to add the Google Cloud SDK command line tools to your $PATH.
""".format(path_rc_path=path_rc_path))

  if not bash_completion and not path_update:
    return

  if not rc_path:

    # figure out what file to edit
    if host_os == platforms.OperatingSystem.LINUX:
      if c_gce.Metadata().connected:
        file_name = '.bash_profile'
      else:
        file_name = '.bashrc'
    elif host_os == platforms.OperatingSystem.MACOSX:
      file_name = '.bash_profile'
    elif host_os == platforms.OperatingSystem.CYGWIN:
      file_name = '.bashrc'
    elif host_os == platforms.OperatingSystem.MSYS:
      file_name = '.profile'
    else:
      file_name = '.bashrc'
    rc_path = os.path.expanduser(os.path.join('~', file_name))

    rc_path_update = console_io.PromptResponse((
        'The Google Cloud SDK installer will now prompt you to update an rc '
        'file to bring the Google Cloud CLIs into your environment.\n\n'
        'Enter path to an rc file to update, or leave blank to use '
        '[{rc_path}]:  ').format(rc_path=rc_path))
    if rc_path_update:
      rc_path = os.path.expanduser(rc_path_update)

  if os.path.exists(rc_path):
    with open(rc_path) as rc_file:
      rc_data = rc_file.read()
      cached_rc_data = rc_data
  else:
    rc_data = ''
    cached_rc_data = ''

  if path_update:
    path_comment = r'# The next line updates PATH for the Google Cloud SDK.'
    path_subre = re.compile(r'\n*'+path_comment+r'\n.*$',
                            re.MULTILINE)

    path_line = "{comment}\nsource '{path_rc_path}'\n".format(
        comment=path_comment, path_rc_path=path_rc_path)
    filtered_data = path_subre.sub('', rc_data)
    rc_data = '{filtered_data}\n{path_line}'.format(
        filtered_data=filtered_data,
        path_line=path_line)

  if bash_completion:
    complete_comment = r'# The next line enables bash completion for gcloud.'
    complete_subre = re.compile(r'\n*'+complete_comment+r'\n.*$',
                                re.MULTILINE)

    complete_line = "{comment}\nsource '{rc_path}'\n".format(
        comment=complete_comment, rc_path=completion_rc_path)
    filtered_data = complete_subre.sub('', rc_data)
    rc_data = '{filtered_data}\n{complete_line}'.format(
        filtered_data=filtered_data,
        complete_line=complete_line)

  if cached_rc_data == rc_data:
    print('No changes necessary for [{rc}].'.format(rc=rc_path))
    return

  if os.path.exists(rc_path):
    rc_backup = rc_path+'.backup'
    print('Backing up [{rc}] to [{backup}].'.format(
        rc=rc_path, backup=rc_backup))
    shutil.copyfile(rc_path, rc_backup)

  with open(rc_path, 'w') as rc_file:
    rc_file.write(rc_data)

  print("""\
[{rc_path}] has been updated.
Start a new shell for the changes to take effect.
""".format(rc_path=rc_path))
