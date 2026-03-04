from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    TEACHER = "teacher"
    PARENT = "parent"


class MembershipType(str, Enum):
    FULL = "full"
    COLLABORATION = "collaboration"


# Role hierarchy: higher index = more privileges
ROLE_HIERARCHY = {
    Role.PARENT: 0,
    Role.TEACHER: 1,
    Role.ORG_ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}
