# -*- coding: utf-8 -*-
"""Package for handling pype command line arguments."""
import os
import sys

import click

# import sys
from .pype_commands import PypeCommands


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--use-version",
              expose_value=False, help="use specified version")
@click.option("--use-staging", is_flag=True,
              expose_value=False, help="use staging variants")
def main(ctx):
    """Pype is main command serving as entry point to pipeline system.

    It wraps different commands together.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(tray)


@main.command()
@click.option("-d", "--dev", is_flag=True, help="Settings in Dev mode")
def settings(dev=False):
    """Show Pype Settings UI."""
    PypeCommands().launch_settings_gui(dev)


@main.command()
def standalonepublisher():
    """Show Pype Standalone publisher UI."""
    PypeCommands().launch_standalone_publisher()


@main.command()
@click.option("-d", "--debug",
              is_flag=True, help=("Run pype tray in debug mode"))
def tray(debug=False):
    """Launch pype tray.

    Default action of pype command is to launch tray widget to control basic
    aspects of pype. See documentation for more information.

    Running pype with `--debug` will result in lot of information useful for
    debugging to be shown in console.
    """
    PypeCommands().launch_tray(debug)


@main.command()
@click.option("-d", "--debug", is_flag=True, help="Print debug messages")
@click.option("--ftrack-url", envvar="FTRACK_SERVER",
              help="Ftrack server url")
@click.option("--ftrack-user", envvar="FTRACK_API_USER",
              help="Ftrack api user")
@click.option("--ftrack-api-key", envvar="FTRACK_API_KEY",
              help="Ftrack api key")
@click.option("--ftrack-events-path",
              envvar="FTRACK_EVENTS_PATH",
              help=("path to ftrack event handlers"))
@click.option("--no-stored-credentials", is_flag=True,
              help="don't use stored credentials")
@click.option("--store-credentials", is_flag=True,
              help="store provided credentials")
@click.option("--legacy", is_flag=True,
              help="run event server without mongo storing")
@click.option("--clockify-api-key", envvar="CLOCKIFY_API_KEY",
              help="Clockify API key.")
@click.option("--clockify-workspace", envvar="CLOCKIFY_WORKSPACE",
              help="Clockify workspace")
def eventserver(debug,
                ftrack_url,
                ftrack_user,
                ftrack_api_key,
                ftrack_events_path,
                no_stored_credentials,
                store_credentials,
                legacy,
                clockify_api_key,
                clockify_workspace):
    """Launch ftrack event server.

    This should be ideally used by system service (such us systemd or upstart
    on linux and window service).

    You have to set either proper environment variables to provide URL and
    credentials or use option to specify them. If you use --store_credentials
    provided credentials will be stored for later use.
    """
    if debug:
        os.environ['PYPE_DEBUG'] = "3"

    PypeCommands().launch_eventservercli(
        ftrack_url,
        ftrack_user,
        ftrack_api_key,
        ftrack_events_path,
        no_stored_credentials,
        store_credentials,
        legacy,
        clockify_api_key,
        clockify_workspace
    )


@main.command()
@click.argument("output_json_path")
@click.option("--project", help="Project name", default=None)
@click.option("--asset", help="Asset name", default=None)
@click.option("--task", help="Task name", default=None)
@click.option("--app", help="Application name", default=None)
def extractenvironments(output_json_path, project, asset, task, app):
    """Extract environment variables for entered context to a json file.

    Entered output filepath will be created if does not exists.

    All context options must be passed otherwise only pype's global
    environments will be extracted.

    Context options are "project", "asset", "task", "app"
    """
    PypeCommands.extractenvironments(
        output_json_path, project, asset, task, app
    )


@main.command()
@click.argument("paths", nargs=-1)
@click.option("-g", "--gui", is_flag=True, help="Run pyblish GUI")
@click.option("-d", "--debug", is_flag=True, help="Print debug messages")
def publish(gui, debug, paths):
    """Start CLI publishing.

    Publish collects json from paths provided as an argument.
    More than one path is allowed.
    """
    if debug:
        os.environ['PYPE_DEBUG'] = '3'
    PypeCommands().publish(gui, list(paths))


@main.command()
@click.option("-d", "--debug", is_flag=True, help="Print debug messages")
@click.option("-p", "--project", required=True,
              help="name of project asset is under")
@click.option("-a", "--asset", required=True,
              help="name of asset to which we want to copy textures")
@click.option("--path", required=True,
              help="path where textures are found",
              type=click.Path(exists=True))
def texturecopy(debug, project, asset, path):
    """Copy specified textures to provided asset path.

    It validates if project and asset exists. Then it will use speedcopy to
    copy all textures found in all directories under --path to destination
    folder, determined by template texture in anatomy. I will use source
    filename and automatically rise version number on directory.

    Result will be copied without directory structure so it will be flat then.
    Nothing is written to database.
    """
    if debug:
        os.environ['PYPE_DEBUG'] = '3'
    PypeCommands().texture_copy(project, asset, path)


@main.command(context_settings={"ignore_unknown_options": True})
@click.option("--app", help="Registered application name")
@click.option("--project", help="Project name",
              default=lambda: os.environ.get('AVALON_PROJECT', ''))
@click.option("--asset", help="Asset name",
              default=lambda: os.environ.get('AVALON_ASSET', ''))
@click.option("--task", help="Task name",
              default=lambda: os.environ.get('AVALON_TASK', ''))
@click.option("--tools", help="List of tools to add")
@click.option("--user", help="Pype user name",
              default=lambda: os.environ.get('PYPE_USERNAME', ''))
@click.option("-fs",
              "--ftrack-server",
              help="Registered application name",
              default=lambda: os.environ.get('FTRACK_SERVER', ''))
@click.option("-fu",
              "--ftrack-user",
              help="Registered application name",
              default=lambda: os.environ.get('FTRACK_API_USER', ''))
@click.option("-fk",
              "--ftrack-key",
              help="Registered application name",
              default=lambda: os.environ.get('FTRACK_API_KEY', ''))
@click.argument('arguments', nargs=-1)
def launch(app, project, asset, task,
           ftrack_server, ftrack_user, ftrack_key, tools, arguments, user):
    """Launch registered application name in Pype context.

    You can define applications in pype-config toml files. Project, asset name
    and task name must be provided (even if they are not used by app itself).
    Optionally you can specify ftrack credentials if needed.

    ARGUMENTS are passed to launched application.

    """
    # TODO: this needs to switch for Settings
    if ftrack_server:
        os.environ["FTRACK_SERVER"] = ftrack_server

    if ftrack_server:
        os.environ["FTRACK_API_USER"] = ftrack_user

    if ftrack_server:
        os.environ["FTRACK_API_KEY"] = ftrack_key

    if user:
        os.environ["PYPE_USERNAME"] = user

    # test required
    if not project or not asset or not task:
        print("!!! Missing required arguments")
        return

    PypeCommands().run_application(app, project, asset, task, tools, arguments)


@main.command()
@click.option("-p", "--path", help="Path to zip file", default=None)
def generate_zip(path):
    """Generate Pype zip from current sources.

    If PATH is not provided, it will create zip file in user data dir.

    """
    PypeCommands().generate_zip(path)


@main.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True))
@click.argument("script", required=True, type=click.Path(exists=True))
def run(script):
    """Run python script in Pype context."""
    import runpy

    if not script:
        print("Error: missing path to script file.")
    else:

        args = sys.argv
        args.remove("run")
        args.remove(script)
        sys.argv = args
        args_string = " ".join(args[1:])
        print(f"... running: {script} {args_string}")
        runpy.run_path(script, run_name="__main__", )
