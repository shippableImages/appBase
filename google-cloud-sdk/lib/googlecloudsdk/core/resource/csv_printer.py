# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.

"""CSV resource printer."""

import os

from googlecloudsdk.core.resource import resource_printer_base


class CsvPrinter(resource_printer_base.ResourcePrinter):
  """A printer for printing CSV data."""

  def __init__(self, *args, **kwargs):
    super(CsvPrinter, self).__init__(*args, by_columns=True, **kwargs)
    self._heading_printed = False

  def _AddRecord(self, record, delimit=False):
    """Prints the current record as CSV.

    Printer attributes:
      noheading: bool, Disable the initial key name heading record.

    Args:
      record: A list of JSON-serializable object columns.
      delimit: bool, Print resource delimiters -- ignored.

    Raises:
      ToolException: A data value has a type error.
    """
    # The CSV heading has three states:
    #   1: No heading, used by ValuePrinter and CSV when 2. and 3. are empty.
    #   2: Heading via AddHeading().
    #   3: Default heading from format labels, if specified.
    if not self._heading_printed:
      self._heading_printed = True
      if 'noheading' not in self._attributes:
        if self._heading:
          labels = self._heading
        else:
          labels = self._column_attributes.Labels()
          if labels:
            labels = [x.lower() for x in labels]
        self._out.write(','.join(labels) + os.linesep)
    line = []
    for col in record:
      if isinstance(col, dict):
        val = ';'.join([str(k) + '=' + str(v)
                        for k, v in sorted(col.iteritems())])
      elif isinstance(col, list):
        val = ';'.join([str(x) for x in col])
      else:
        val = str(col)
      line.append(val)
    self._out.write(','.join(line))
    self._out.write(os.linesep)


class ValuePrinter(CsvPrinter):
  """A printer for printing value data.

  This is CSV with no heading.
  """

  def __init__(self, *args, **kwargs):
    super(ValuePrinter, self).__init__(*args, **kwargs)
    self._heading_printed = True
