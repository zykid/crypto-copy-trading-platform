from pydantic import BaseModel, ConfigDict, model_validator


class PermissionCreate(BaseModel):
    grantee_user_id: str
    view_only: bool = False
    copy_follow: bool = False
    pause_follow: bool = False
    edit_copy_rule: bool = False
    trade_manual: bool = False

    @model_validator(mode="after")
    def require_one_permission(self) -> "PermissionCreate":
        if not any(
            [
                self.view_only,
                self.copy_follow,
                self.pause_follow,
                self.edit_copy_rule,
                self.trade_manual,
            ]
        ):
            raise ValueError("at least one permission must be enabled")
        return self


class PermissionUpdate(BaseModel):
    view_only: bool | None = None
    copy_follow: bool | None = None
    pause_follow: bool | None = None
    edit_copy_rule: bool | None = None
    trade_manual: bool | None = None


class PermissionResponse(BaseModel):
    id: str
    owner_user_id: str
    grantee_user_id: str
    view_only: bool
    copy_follow: bool
    pause_follow: bool
    edit_copy_rule: bool
    trade_manual: bool

    model_config = ConfigDict(from_attributes=True)
