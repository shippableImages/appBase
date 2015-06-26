# Copyright 2015 Google Inc. All Rights Reserved.

"""Default resource projection transform functions.

A resource projection transform function converts a JSON-serializable resource
to a string value. This module contains transform functions that may be used in
printer resource projection expressions.
"""

import cStringIO
import re

from googlecloudsdk.core.util import console_attr


def BaseName(r, undefined=''):
  """Projection helper function - returns the file path basename.

  Args:
    r: A url or unix/windows file path.
    undefined: This value is returned if r or the basename is empty.

  Returns:
    The last path component.
  """
  if not r:
    return undefined
  s = str(r)
  for separator in ('/', '\\'):
    i = s.rfind(separator)
    if i >= 0:
      return s[i + 1:]
  return s or undefined


def Color(r, red=None, yellow=None, green=None, blue=None, **kwargs):
  """Projection helper function - colorizes resource string value.

  The resource string is searched for an re pattern match in Roy.G.Biv order.
  The first pattern that matches colorizes the resource string with that color.

  Args:
    r: A JSON-serializable object.
    red: Color red resource value pattern.
    yellow: Color yellow resource value pattern.
    green: Color green resource value pattern.
    blue: Color blue resource value pattern.
    **kwargs: console_attr.Colorizer() kwargs.

  Returns:
    A console_attr.Colorizer() object if any color substring matches, r
    otherwise.
  """
  string = str(r)
  for color, pattern in (('red', red), ('yellow', yellow), ('green', green),
                         ('blue', blue)):
    if pattern and re.search(pattern, string):
      return console_attr.Colorizer(string, color, **kwargs)
  return string


def Group(r, *args):
  """Projection helper function - returns a [...] grouped list.

  Each group is enclosed in [...]. The first item separator is ':', subsequent
  separators are ','.
    [item1] [item1] ...
    [item1: item2] ... [item1: item2]
    [item1: item2, item3] ... [item1: item2, item3]

  Args:
    r: A JSON-serializable object.
    *args: Optional attribute names to select from the list. Otherwise
      the string value of each list item is selected.

  Returns:
    The [...] grouped formatted list, [] if r is empty.
  """
  if not r:
    return '[]'
  buf = cStringIO.StringIO()
  sep = None
  for item in r:
    if sep:
      buf.write(sep)
    else:
      sep = ' '
    if not args:
      buf.write('[%s]' % str(item))
    else:
      buf.write('[')
      sub = None
      for attr in args:
        if sub:
          buf.write(sub)
          sub = ', '
        else:
          sub = ': '
        buf.write(str(getattr(item, attr)))
      buf.write(']')
  return buf.getvalue()


def Iso(r, undefined='T'):
  """Projection helper function - returns r.isoformat().

  Args:
    r: A JSON-serializable object.
    undefined: Returns this if r does not have an isoformat() attribute.

  Returns:
    r.isformat() or undefined if not defined.
  """
  return r.isoformat() if hasattr(r, 'isoformat') else undefined


def List(r, undefined=None):
  """Projection helper function - returns a comma separated list.

  Args:
    r: A JSON-serializable object.
    undefined: Return this if r is empty.

  Returns:
    The comma separated formatted list, undefined if r is empty.
  """
  return ', '.join(map(str, r)) if r else undefined


def Resolution(r, undefined='', transpose=False):
  """Projection helper function - returns human readable XY resolution.

  Args:
    r: object, A JSON-serializable object containing an x/y resolution.
    undefined: Returns this if a recognizable resolution was not found.
    transpose: Returns the y/x resolution if True.

  Returns:
    The human readable x/y resolution for r if it contains members that
      specify width/height, col/row, col/line, or x/y resolution. Returns
      undefined if no resolution found.
  """
  names = (
      ('width', 'height'),
      ('screenx', 'screeny'),
      ('col', 'row'),
      ('col', 'line'),
      ('x', 'y'),
      )

  # Collect the lower case candidate member names.
  mem = {}
  for m in r if isinstance(r, dict) else dir(r):
    if not m.startswith('__') and not m.endswith('__'):
      mem[m.lower()] = m

  def _Dimension(d):
    """Gets the resolution dimension for d.

    Args:
      d: The dimension name substring to get.

    Returns:
      The resolution dimension matching d or None.
    """
    for m in mem:
      if d in m:
        return r[mem[d]] if isinstance(r, dict) else getattr(r, mem[d])
    return None

  # Check member name pairwise matches in order from least to most ambiguous.
  for name_x, name_y in names:
    x = _Dimension(name_x)
    if x is None:
      continue
    y = _Dimension(name_y)
    if y is None:
      continue
    return ('{y} x {x}' if transpose else '{x} x {y}').format(x=x, y=y)
  return undefined


def Size(r, zero='0'):
  """Projection helper function - returns human readable size in bytes.

  Args:
    r: A size in bytes.
    zero: Returns this if size==0. Ignored if None.

  Returns:
    A human readable scaled size in bytes.
  """
  if not r and zero is not None:
    return zero
  size = float(r or 0)
  the_unit = 'TiB'
  for unit in ['bytes', 'KiB', 'MiB', 'GiB']:
    if size < 1024.0:
      the_unit = unit
      break
    size /= 1024.0
  if size == int(size):
    return '%d %s' % (size, the_unit)
  else:
    return '%3.1f %s' % (size, the_unit)


def Uri(r, undefined='.'):
  """Projection helper function - returns the URI for r.

  Args:
    r: A JSON-serializable object.
    undefined: Returns this if a the URI for r cannot be determined.

  Returns:
    The URI for r or undefined if not defined.
  """
  if hasattr(r, 'selfLink'):
    return r.selfLink
  elif hasattr(r, 'SelfLink'):
    return r.SelfLink
  if r:
    for name in ['selfLink', 'SelfLink', 'instance']:
      if name in r:
        return r[name]
  return undefined


def YesNo(r, yes=None, no='No'):
  """Projection helper function - returns no if r is empty, yes or r otherwise.

  Args:
    r: A JSON-serializable object.
    yes: If r is not empty then returns yes or r.
    no: Returns this string if r is empty.

  Returns:
    yes or r if r is not empty, no otherwise.
  """
  return (r if yes is None else yes) if r else no
