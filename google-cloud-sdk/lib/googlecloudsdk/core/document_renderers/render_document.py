# Copyright 2015 Google Inc. All Rights Reserved.

"""Cloud SDK markdown document renderer.

This module marshals markdown renderers to convert Cloud SDK markdown to text,
HTML and manpage documents. The renderers are self-contained, allowing the
Cloud SDK runtime to generate documents on the fly for all target architectures.

The _MarkdownConverter class parses markdown from an input stream and renders it
using the Renderer class. The Renderer member functions provide an abstract
document model that matches markdown entities to the output document, e.g., font
embellishment, section headings, lists, hanging indents, text margins, tables.
There is a Renderer derived class for each output style that writes the result
on an output stream.
"""

import argparse
import sys

from googlecloudsdk.core.document_renderers import devsite_renderer
from googlecloudsdk.core.document_renderers import html_renderer
from googlecloudsdk.core.document_renderers import man_renderer
from googlecloudsdk.core.document_renderers import markdown_renderer
from googlecloudsdk.core.document_renderers import renderer
from googlecloudsdk.core.document_renderers import text_renderer


class _ListElementState(object):
  """List element state.

  Attributes:
    bullet: True if the current element is a bullet.
    ignore_line: The number of blank line requests to ignore.
    level: List element nesting level counting from 0.
  """

  def __init__(self):
    self.bullet = False
    self.ignore_line = 0
    self.level = 0


class _MarkdownConverter(object):
  """Reads markdown and renders to a document.

  Attributes:
    _EMPHASIS: The font emphasis attribute dict indexed by markdown character.
    _buf: The current output line.
    _depth: List nesting depth counting from 0.
    _edit: True if NOTES edits are required.
    _example: The current example indentation space count.
    _fin: The markdown input stream.
    _line: The current input line.
    _lists: _ListElementState list element state stack indexed by _depth.
    _next_example: The next example indentation space count.
    _notes: Additional text for the NOTES section.
    _paragraph: True if the last line was ``+'' paragraph at current indent.
    _next_paragraph: The next line starts a new paragraph at same indentation.
    _renderer: The document_renderer.Renderer subclass.
  """
  _EMPHASIS = {'*': renderer.BOLD, '_': renderer.ITALIC, '`': renderer.CODE}

  def __init__(self, style_renderer, fin=sys.stdin, notes=None):
    """Initializes the converter.

    Args:
      style_renderer: The document_renderer.Renderer subclass.
      fin: The markdown input stream.
      notes: Optional sentences for the NOTES section.
    """
    self._renderer = style_renderer
    self._buf = ''
    self._fin = fin
    self._notes = notes
    self._edit = self._notes
    self._lists = [_ListElementState()]
    self._depth = 0
    self._example = 0
    self._next_example = 0
    self._paragraph = False
    self._next_paragraph = False
    self._line = None

  def _Anchor(self, buf, i):
    """Checks for link:target[text] hyperlink anchor markdown.

    Hyperlink anchors are of the form:
      <link> ':' <target> [ '[' <text> ']' ]
    For example:
      http://www.google.com[Google Search]
    The underlying renderer determines how the parts are displayed.

    Args:
      buf: Input buffer.
      i: The buf[] index of ':'.

    Returns:
      (i, back, target, text)
        i: The buf[] index just past the link, 0 if no link.
        back: The number of characters to retain before buf[i].
        target: The link target.
        text: The link text.
    """
    if i >= 3 and buf[i - 3:i] == 'ftp':
      back = 3
      target_beg = i - 3
    elif i >= 4 and buf[i - 4:i] == 'http':
      back = 4
      target_beg = i - 4
    elif i >= 4 and buf[i - 4:i] == 'link':
      back = 4
      target_beg = i + 1
    elif i >= 5 and buf[i - 5:i] == 'https':
      back = 5
      target_beg = i - 5
    elif i >= 6 and buf[i - 6:i] == 'mailto':
      back = 6
      target_beg = i - 6
    else:
      return 0, 0, None, None
    text_beg = 0
    text_end = 0
    nesting = 0
    j = i
    while j < len(buf):
      if buf[j] == '[':
        if not text_beg:
          text_beg = j + 1
        nesting += 1
      if buf[j] == ']':
        nesting -= 1
        if nesting == 0:
          text_end = j
          break
        if nesting < 0:
          break
      j += 1
    if not text_end:
      return 0, 0, None, None
    return (text_end + 1, back, buf[target_beg:text_beg - 1],
            buf[text_beg:text_end])

  def _Attributes(self):
    """Converts inline markdown attributes in self._buf.

    Returns:
      A string with markdown attributes converted to render properly.
    """
    # String append used on ret below because of anchor text look behind.
    ret = ''
    if self._buf:
      buf = self._renderer.Escape(self._buf)
      self._buf = ''
      i = 0
      while i < len(buf):
        c = buf[i]
        if c == ':':
          j, back, target, text = self._Anchor(buf, i)
          if j:
            ret = ret[:-back]
            i = j - 1
            c = self._renderer.Link(target, text)
        elif c in '*_`':
          # Treating some apparent font embelishment markdown as literal input
          # is the hairiest part of markdown. This code catches the common
          # programming clash of '*' as a literal globbing character in path
          # matching examples. It basically works for the current use cases.
          l = buf[i - 1] if i else ' '  # The char to the left.
          r = buf[i + 1] if i < len(buf) - 1 else ' '  # The char to the right.
          if r == c:
            c += c
            i += 1
          elif c == '*' and l in ' /' and r in ' ./' or l in ' /' and r in ' .':
            pass
          elif l.isalnum() and r.isalnum():
            pass
          else:
            c = self._renderer.Font(self._EMPHASIS[c])
        ret += c
        i += 1
    return ret

  def _Example(self, line):
    """Renders line as an example.

    Args:
      line: The example line.
    """
    if line:
      self._buf = line
      self._renderer.Example(self._Attributes())

  def _Fill(self):
    """Sends self._buf to the renderer and clears self._buf."""
    if self._buf:
      self._renderer.Fill(self._Attributes())

  def _ReadLine(self):
    """Reads and possibly preprocesses the next markdown line fron self._fin.

    Returns:
      The next markdown input line.
    """
    return self._fin.readline()

  def _ConvertMarkdownToMarkdown(self):
    """Generates markdown with additonal NOTES if requested."""
    if not self._edit:
      self._renderer.Write(self._fin.read())
      return
    while True:
      line = self._ReadLine()
      if not line:
        break
      self._renderer.Write(line)
      if self._notes and line == '== NOTES ==\n':
        self._renderer.Write('\n' + self._notes + '\n')
        self._notes = ''
    if self._notes:
      self._renderer.Write('\n\n== NOTES ==\n\n' + self._notes + '\n')

  def _ConvertBlankLine(self, i):
    """Detects and converts a blank markdown line (length 0).

    Resets the indentation to the default and emits a blank line. Multiple
    blank lines are suppressed in the output.

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is a blank markdown, i otherwise.
    """
    if self._line:
      return i
    self._Fill()
    if self._lists[self._depth].bullet:
      self._renderer.List(0)
      self._depth -= 1
    if self._lists[self._depth].ignore_line:
      self._lists[self._depth].ignore_line -= 1
    if not self._depth or not self._lists[self._depth].ignore_line:
      self._renderer.Line()
    return -1

  def _ConvertParagraph(self, i):
    """Detects and converts + markdown line (length 1).

    Emits a blank line but retains the current indent.

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is a '+' markdown, i otherwise.
    """
    if len(self._line) != 1 or self._line[0] != '+':
      return i
    self._Fill()
    self._renderer.Line()
    self._next_paragraph = True
    return -1

  def _ConvertHeading(self, i):
    """Detects and converts a markdown heading line.

    = level-1 =
    == level-2 ==

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is a heading markdown, i otherwise.
    """
    j = i
    while (i < len(self._line) and self._line[i] == '=' and
           self._line[-(i + 1)] == '='):
      i += 1
    if i <= 0 or self._line[i] != ' ' or self._line[-(i + 1)] != ' ':
      return j
    self._Fill()
    self._buf = self._line[i + 1:-(i + 1)]
    heading = self._Attributes()
    self._renderer.Heading(i, heading)
    self._depth = 0
    if heading in ['NAME', 'SYNOPSIS']:
      # TODO(user): Delete this section when markdown.py is updated ...
      old_style = False
      # TODO(user): ... end of section.
      while True:
        self._buf = self._ReadLine()
        if not self._buf:
          break
        self._buf = self._buf.rstrip()
        # TODO(user): Delete this section when markdown.py is updated ...
        if len(self._buf) > 2 and self._buf[-1] == ':' and self._buf[-2] == ':':
          self._buf = self._buf[:-2]
          old_style = True
        # TODO(user): ... end of section.
        if self._buf:
          self._renderer.Synopsis(self._Attributes())
          # TODO(user): Delete this section when markdown.py is updated ...
          if old_style and heading == 'SYNOPSIS':
            self._ReadLine()
            self._ReadLine()
          # TODO(user): ... end of section.
          break
    elif self._notes and heading == 'NOTES':
      self._buf = self._notes
      self._notes = None
    return -1

  def _ConvertTable(self, i):
    """Detects and converts a sequence of markdown table lines.

    This method will consume multiple input lines if the current line is a
    table heading. The table markdown sequence is:

       [...format="csv"...]
       |====*
       col-1-data-item,col-2-data-item...
         ...
       <blank line ends table>

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input lines are table markdown, i otherwise.
    """
    if (self._line[0] != '[' or self._line[-1] != ']' or
        'format="csv"' not in self._line):
      return i
    self._renderer.Table(self._line)
    delim = 2
    while True:
      self._buf = self._ReadLine()
      if not self._buf:
        break
      self._buf = self._buf.rstrip()
      if self._buf.startswith('|===='):
        delim -= 1
        if delim <= 0:
          break
      else:
        self._renderer.Table(self._Attributes())
    self._buf = ''
    self._renderer.Table(None)
    return -1

  def _ConvertDefinitionList(self, i):
    """Detects and converts a definition list item markdown line.

         level-1::
         level-2:::

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is a definition list item markdown, i otherwise.
    """
    while i < len(self._line) and self._line[i] == ' ':
      i += 1
    if i:
      return i
    j = self._line.find('::')
    if j < 0:
      return i
    level = 1
    i = j + 2
    while i < len(self._line) and self._line[i] == ':':
      i += 1
      level += 1
    if (self._lists[self._depth].bullet or
        self._lists[self._depth].level < level):
      self._depth += 1
      if self._depth >= len(self._lists):
        self._lists.append(_ListElementState())
    else:
      while self._lists[self._depth].level > level:
        self._depth -= 1
    self._lists[self._depth].bullet = False
    self._lists[self._depth].ignore_line = 2
    self._lists[self._depth].level = level
    while i < len(self._line) and self._line[i] == ' ':
      i += 1
    self._Fill()
    self._buf = self._line[:j]
    self._renderer.List(self._depth, self._Attributes())
    if i < len(self._line):
      self._buf += self._line[i:]
    return -1

  def _ConvertBulletList(self, i):
    """Detects and converts a bullet list item markdown line.

    The list item indicator may be '-' or '*'. nesting by multiple indicators:

        - level-1
        -- level-2
        - level-1

    or nesting by indicator indentation:

        - level-1
         - level-2
        - level-1

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is a bullet list item markdown, i otherwise.
    """
    if self._line[i] not in '-*':
      return i
    bullet = self._line[i]
    level = i / 2
    j = i
    while j < len(self._line) and self._line[j] == bullet:
      j += 1
      level += 1
    if j >= len(self._line) or self._line[j] != ' ':
      return i
    if (self._lists[self._depth].bullet and
        self._lists[self._depth].level >= level):
      while self._lists[self._depth].level > level:
        self._depth -= 1
    else:
      self._depth += 1
      if self._depth >= len(self._lists):
        self._lists.append(_ListElementState())
    self._lists[self._depth].bullet = True
    self._lists[self._depth].ignore_line = 0
    self._lists[self._depth].level = level
    self._Fill()
    self._renderer.List(self._depth)
    while j < len(self._line) and self._line[j] == ' ':
      j += 1
    self._buf += self._line[j:]
    return -1

  def _ConvertExample(self, i):
    """Detects and converts an example markdown line.

    Example lines are indented by one or more space characters.

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is is an example line markdown, i otherwise.
    """
    if not i or self._depth and not (self._example or self._paragraph):
      return i
    self._Fill()
    if not self._example or self._example > i:
      self._example = i
    self._Example(self._line[self._example:])
    self._next_example = self._example
    return -1

  def _ConvertEndOfList(self, i):
    """Detects and converts an end of list markdown line.

    Args:
      i: The current character index in self._line.

    Returns:
      -1 if the input line is an end of list markdown, i otherwise.
    """
    if i or not self._depth:
      return i
    if self._lists[self._depth].ignore_line > 1:
      self._lists[self._depth].ignore_line -= 1
    if not self._lists[self._depth].ignore_line:
      self._Fill()
      self._renderer.List(0)
      self._depth = 0
    return i  # More conversion possible.

  def _ConvertRemainder(self, i):
    """Detects and converts any remaining markdown text.

    The input line is always consumed by this method. It should be the last
    _Convert*() method called for each input line.

    Args:
      i: The current character index in self._line.

    Returns:
      -1
    """
    self._buf += ' ' + self._line[i:]
    return -1

  def _Finish(self):
    """Flushes the fill buffer and checks for NOTES.

    A previous _ConvertHeading() will have cleared self._notes if a NOTES
    section has already been seen.
    """
    self._Fill()
    if self._notes:
      self._renderer.Line()
      self._renderer.Heading(2, 'NOTES')
      self._buf += self._notes
      self._Fill()
    self._renderer.Finish()

  def Run(self):
    """Renders the markdown from fin to out."""
    if isinstance(self._renderer, markdown_renderer.MarkdownRenderer):
      self._ConvertMarkdownToMarkdown()
      return
    while True:
      self._example = self._next_example
      self._next_example = 0
      self._paragraph = self._next_paragraph
      self._next_paragraph = False
      self._line = self._ReadLine()
      if not self._line:
        break
      self._line = self._line.rstrip()
      i = 0
      for detect_and_convert in [
          self._ConvertBlankLine,
          self._ConvertParagraph,
          self._ConvertHeading,
          self._ConvertTable,
          self._ConvertDefinitionList,
          self._ConvertBulletList,
          self._ConvertExample,
          self._ConvertEndOfList,
          self._ConvertRemainder]:
        i = detect_and_convert(i)
        if i < 0:
          break
    self._Finish()


_STYLES = {'devsite': devsite_renderer.DevSiteRenderer,
           'html': html_renderer.HTMLRenderer,
           'man': man_renderer.ManRenderer,
           'markdown': markdown_renderer.MarkdownRenderer,
           'text': text_renderer.TextRenderer}


def RenderDocument(style='text', fin=None, out=None, width=80, notes=None,
                   title=None):
  """Renders markdown to a selected document style.

  Args:
    style: The rendered document style name, must be one of the _STYLES keys.
    fin: The input stream containing the markdown.
    out: The output stream for the rendered document.
    width: The page width in characters.
    notes: Optional sentences inserted in the NOTES section.
    title: The document title.

  Raises:
    ValueError: The markdown style was unknown.
  """
  if style not in _STYLES:
    raise ValueError('Unknown markdown document style [{style}].'.format(
        style=style))
  style_renderer = _STYLES[style](out=out or sys.stdout, title=title,
                                  width=width)
  _MarkdownConverter(style_renderer, fin=fin or sys.stdin, notes=notes).Run()


def main(argv):
  """Standalone markdown document renderer."""

  styles = sorted(_STYLES.keys())

  parser = argparse.ArgumentParser(
      description='Renders markdown on the standard input into a document on '
      'the standard output.')

  parser.add_argument(
      '--notes',
      metavar='SENTENCES',
      help='Inserts SENTENCES into the NOTES section which is created if '
      'needed.')

  parser.add_argument(
      '--style',
      metavar='STYLE',
      choices=styles,
      default='text',
      help='The output style. Must be one of {styles}. The default is '
      'text.'.format(styles=styles))

  parser.add_argument(
      '--title',
      metavar='TITLE',
      help='The document title.')

  args = parser.parse_args(argv[1:])

  RenderDocument(args.style, notes=args.notes, title=args.title)


if __name__ == '__main__':
  main(sys.argv)
