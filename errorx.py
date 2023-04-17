class BussinessError(RuntimeError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class UnpaidError(BussinessError):
    def __init__(self, *args: object) -> None:
        super().__init__("需要支付影响力后才能下载", *args)
        

class UnfollowedError(BussinessError):
    def __init__(self, *args: object) -> None:
        super().__init__("需要关注作者后才能下载" ,*args)