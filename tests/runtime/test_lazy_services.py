import threading
from concurrent.futures import ThreadPoolExecutor

from xenix.services.lazy_services import lazy_service


def test_concurrent_first_use_constructs_one_service():
    callers = threading.Barrier(5)
    entered = threading.Event()
    release = threading.Event()
    created = []

    class Service:
        def identity(self):
            return id(self)

    def create():
        entered.set()
        assert release.wait(5)
        service = Service()
        created.append(service)
        return service

    service = lazy_service(create)

    def access():
        callers.wait(timeout=5)
        return service.identity()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(access) for _ in range(4)]
        try:
            callers.wait(timeout=5)
            assert entered.wait(5)
        finally:
            release.set()
        identities = [future.result(timeout=5) for future in futures]
    assert len(created) == 1
    assert identities == [id(created[0])] * 4
