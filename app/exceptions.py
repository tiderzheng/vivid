class VividError(RuntimeError):
    pass


class BilibiliSessdataExpiredError(VividError):
    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or ""
        message = "Bilibili SESSDATA appears expired or invalid."
        if self.detail:
            message = f"{message} {self.detail}"
        super().__init__(message)
