import click

# from openpype.lib import get_openpype_execute_args
# from openpype.lib.execute import run_detached_process
# from openpype.modules import OpenPypeModule, ITrayAction, IHostAddon
from ayon_core.addon import AYONAddon, IHostAddon, ITrayAction


class BatchPublishAddon(AYONAddon, IHostAddon, ITrayAction):
    label = "Batch Publisher"
    name = "batchpublisher"
    host_name = "batchpublisher"

    def initialize(self, modules_settings):
        self.enabled = True
        # UI which must not be created at this time
        self._dialog = None

    def tray_init(self):
        return

    def on_action_trigger(self):
        self.show_dialog()
        # self.run_batchpublisher()

    def connect_with_modules(self, enabled_modules):
        """Collect publish paths from other modules."""
        return

    # def run_batchpublisher(self):
    #     name = "traypublisher"
    #     args = get_openpype_execute_args(
    #         "module", name, "launch"
    #         # "module", self.name, "launch"
    #     )
    #     print("ARGS" , args)
    #     run_detached_process(args)

    def cli(self, click_group):
        click_group.add_command(cli_main)

    def _create_dialog(self):
        # # Don't recreate dialog if already exists
        # if self._dialog is not None:
        #     return

        from importlib import reload

        import ayon_core.hosts.batchpublisher.controller
        import ayon_core.hosts.batchpublisher.ui.batch_publisher_model
        import ayon_core.hosts.batchpublisher.ui.batch_publisher_delegate
        import ayon_core.hosts.batchpublisher.ui.batch_publisher_view
        import ayon_core.hosts.batchpublisher.ui.window

        # TODO: These lines are only for testing current branch
        reload(ayon_core.hosts.batchpublisher.controller)
        reload(ayon_core.hosts.batchpublisher.ui.batch_publisher_model)
        reload(
            ayon_core.hosts.batchpublisher.ui.batch_publisher_delegate)
        reload(ayon_core.hosts.batchpublisher.ui.batch_publisher_view)
        reload(ayon_core.hosts.batchpublisher.ui.window)

        # from ayon_core.hosts.batchpublisher.ui.window \
        #     import BatchPublisherWindow
        self._dialog = ayon_core.hosts.batchpublisher.ui.window. \
            BatchPublisherWindow()

    def show_dialog(self):
        """Show dialog with connected modules.
        This can be called from anywhere but can also crash in headless mode.
        There is no way to prevent addon to do invalid operations if he's
        not handling them.
        """
        # Make sure dialog is created
        self._create_dialog()
        # Show dialog
        self._dialog.show()


@click.group(BatchPublishAddon.name, help="BatchPublisher related commands.")
def cli_main():
    pass


@cli_main.command()
def launch():
    """Launch BatchPublisher tool UI."""
    print("LAUNCHING BATCH PUBLISHER")
    from ayon_core.hosts.batchpublisher.ui import window
    window.main()