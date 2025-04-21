import grp
import pwd
from src.settings import logger


class UnprivilegedUserGroup:
    def __init__(self):
        self.possible_users = ["nobody", "www-data", "daemon", "nginx", "apache"]
        self.possible_groups = [
            "nobody",
            "nogroup",
            "www-data",
            "daemon",
            "nginx",
            "apache",
        ]
        self.user, self.group = self._get_user_group()

    def _get_user_group(self):
        user = self._get_user()
        group = self._get_group()

        if not user or not group:
            return "65534", "65534"
        return user, group

    def _get_user(self):
        for username in self.possible_users:
            try:
                return pwd.getpwnam(username).pw_name
            except KeyError:
                continue
        return None

    def _get_group(self):
        for groupname in self.possible_groups:
            try:
                return grp.getgrnam(groupname).gr_name
            except KeyError:
                continue
        return None

    def get_user(self):
        return self.user

    def get_group(self):
        return self.group


try:
    unprivileged = UnprivilegedUserGroup()
    UNPRIVILEGED_USER = unprivileged.get_user()
    UNPRIVILEGED_GROUP = unprivileged.get_group()
except Exception as e:
    logger.error(f"Error finding unprivileged user/group: {e}")
    raise RuntimeError(
        "Failed to find unprivileged user/group. Please check your system configuration."
    )
