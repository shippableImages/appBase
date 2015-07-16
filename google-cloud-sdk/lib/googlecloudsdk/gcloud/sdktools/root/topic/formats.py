# Copyright 2014 Google Inc. All Rights Reserved.

"""Resource formats supplementary help."""

from googlecloudsdk.calliope import base


class Formats(base.Command):
  """Resource formats supplementary help."""

  def Run(self, args):
    self.cli.Execute(args.command_path[1:] + ['--document=style=topic'])
    return None

  detailed_help = {

      'DESCRIPTION': """\
          {description}

          === Formats ===

          Resource printing formats are specified by the --format=_FORMAT_ flag.
          The supported formats are:

          link:www.yaml.org[yaml]::
          YAML ain't markup language.

          link:www.json.org[json]::
          JavaScript Object Notation.

          text::
          Flattened YAML
          """,

      'EXAMPLES': """\
          List the compute instances resources in JSON format:

            $ gcloud compute instances list --format=json
          """,
      }
