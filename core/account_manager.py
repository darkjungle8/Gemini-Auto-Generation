import os
import logging

logger = logging.getLogger(__name__)


class AccountManager:
    """Manages Chrome profile accounts for a single browser window.

    Each 'account' is a separate Chrome user-data-dir to avoid lock conflicts
    when running multiple Chrome instances in parallel.

    Directory structure:
        base_dir/
            account_01/      <- user-data-dir for account 1
                Default/     <- Chrome profile data
            account_02/      <- user-data-dir for account 2
                Default/
    """

    def __init__(self, profile_base_dir, account_names):
        self.profile_base_dir = profile_base_dir
        self.account_names = list(account_names)
        self.current_index = 0
        self.exhausted = set()

    def get_current_account(self):
        """Return the name of the current account, or None if all exhausted."""
        if self.current_index >= len(self.account_names):
            return None
        return self.account_names[self.current_index]

    def get_current_user_data_dir(self):
        """Return the full user-data-dir path for the current account."""
        account = self.get_current_account()
        if account:
            return os.path.join(self.profile_base_dir, account)
        return None

    def mark_exhausted(self):
        """Mark the current account's free quota as used up."""
        account = self.get_current_account()
        if account:
            self.exhausted.add(account)
            logger.info(f"Account '{account}' marked as quota-exhausted")

    def switch_to_next(self):
        """Switch to the next available account.
        Returns True if a new account is available, False otherwise.
        """
        self.mark_exhausted()
        self.current_index += 1
        next_account = self.get_current_account()
        if next_account:
            logger.info(f"Switched to account: {next_account}")
            return True
        logger.warning("No more accounts available for this window")
        return False

    def has_available_accounts(self):
        return self.current_index < len(self.account_names)

    def reset(self):
        self.current_index = 0
        self.exhausted.clear()

    @staticmethod
    def scan_accounts(profile_base_dir):
        """Scan the base directory for Chrome account folders."""
        accounts = []
        if not os.path.isdir(profile_base_dir):
            return accounts
        for item in sorted(os.listdir(profile_base_dir)):
            if item.startswith("."):
                continue
            item_path = os.path.join(profile_base_dir, item)
            if os.path.isdir(item_path):
                accounts.append(item)
        return accounts

    @staticmethod
    def create_account_dir(profile_base_dir, account_name):
        """Create a new account directory."""
        account_dir = os.path.join(profile_base_dir, account_name)
        os.makedirs(account_dir, exist_ok=True)
        logger.info(f"Created account directory: {account_dir}")
        return account_dir
