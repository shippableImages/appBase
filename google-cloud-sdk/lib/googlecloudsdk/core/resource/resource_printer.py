# Copyright 2015 Google Inc. All Rights Reserved.

"""Methods for formatting and printing Python objects.

Each printer has three main attributes, all accessible as strings in the
--format='NAME[ATTRIBUTES](PROJECTION)' option:

  NAME: str, The printer name.

  [ATTRIBUTES]: str, An optional [no]name[=value] list of attributes. Unknown
    attributes are silently ignored. Attributes are added to a printer local
    dict indexed by name.

  (PROJECTION): str, List of resource names to be included in the output
    resource. Unknown names are silently ignored. Resource names are
    '.'-separated key identifiers with an implicit top level resource name.

Example:

  gcloud compute instances list \
      --format='table[box](name, networkInterfaces[0].networkIP)'
"""

from googlecloudsdk.core import exceptions as core_exceptions
from googlecloudsdk.core.resource import csv_printer
from googlecloudsdk.core.resource import flaml_printer
from googlecloudsdk.core.resource import json_printer
from googlecloudsdk.core.resource import list_printer
from googlecloudsdk.core.resource import resource_projector
from googlecloudsdk.core.resource import resource_transform
from googlecloudsdk.core.resource import table_printer
from googlecloudsdk.core.resource import yaml_printer


class Error(core_exceptions.Error):
  """Exceptions for this module."""


class UnknownFormatError(Error):
  """UnknownFormatError is thrown for unknown format names."""


_FORMATTERS = {
    'csv': csv_printer.CsvPrinter,
    'flaml': flaml_printer.FlamlPrinter,
    'json': json_printer.JsonPrinter,
    'list': list_printer.ListPrinter,
    'table': table_printer.TablePrinter,
    'text': flaml_printer.FlamlPrinter,  # TODO(user): Drop from compute.
    'value': csv_printer.ValuePrinter,
    'yaml': yaml_printer.YamlPrinter,
}


_TRANSFORMS = {
    'basename': resource_transform.BaseName,
    'color': resource_transform.Color,
    'group': resource_transform.Group,
    'iso': resource_transform.Iso,
    'list': resource_transform.List,
    'resolution': resource_transform.Resolution,
    'size': resource_transform.Size,
    'uri': resource_transform.Uri,
    'yesno': resource_transform.YesNo,
}


def SupportedFormats():
  """Returns a sorted list of supported format names."""
  return sorted(_FORMATTERS)


def Printer(print_format, out=None, defaults=None):
  """Returns a resource printer given a format string.

  Args:
    print_format: The _FORMATTERS name with optional attributes and projection.
    out: Output stream, log.out if None.
    defaults: Optional resource_projection_spec.ProjectionSpec defaults.

  Raises:
    UnknownFormatError: The print_format is invalid.

  Returns:
    An initialized ResourcePrinter class.
  """

  projector = resource_projector.Compile(expression=print_format,
                                         defaults=defaults,
                                         symbols=_TRANSFORMS)
  projection = projector.Projection()
  printer_name = projection.Name()
  printer_class = _FORMATTERS.get(printer_name, None)
  if not printer_class:
    raise UnknownFormatError('Format must be one of {0}; received [{1}]'.format(
        ', '.join(SupportedFormats()), printer_name))
  printer = printer_class(out=out,
                          name=printer_name,
                          attributes=projection.Attributes(),
                          column_attributes=projection,
                          process_record=projector.Evaluate)
  projector.SetByColumns(printer.ByColumns())
  return printer


def _IsListLike(resources):
  """Checks if resources is a list-like iterable object.

  Args:
    resources: The object to check.

  Returns:
    True if resources is a list-like iterable object.
  """
  return (isinstance(resources, list) or
          hasattr(resources, '__iter__') and hasattr(resources, 'next'))


def Print(resources, print_format, out=None, defaults=None, single=False):
  """Prints the given resources.

  Args:
    resources: A singleton or list of JSON-serializable Python objects.
    print_format: The _FORMATTER name with optional projection expression.
    out: Output stream, log.out if None.
    defaults: Optional resource_projection_spec.ProjectionSpec defaults.
    single: If True then resources is a single item and not a list.
      For example, use this to print a single object as JSON.
  """
  printer = Printer(print_format, out=out, defaults=defaults)

  # Resources may be a generator and since generators can raise exceptions, we
  # have to call Finish() in the finally block to make sure that the resources
  # we've been able to pull out of the generator are printed before control is
  # given to the exception-handling code.
  try:
    if resources:
      if single or not _IsListLike(resources):
        printer.AddRecord(resources, delimit=False)
      else:
        for resource in resources:
          printer.AddRecord(resource)
  finally:
    printer.Finish()
