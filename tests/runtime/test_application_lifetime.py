from xenix.application_lifetime import ApplicationLifetime


def test_partial_startup_releases_all_acquired_resources_once(caplog):
    released = []
    lifetime = ApplicationLifetime()
    lifetime.add_cleanup("database", lambda: released.append("database"))

    def broken_service_close():
        released.append("service")
        raise RuntimeError("service close failed")

    lifetime.add_cleanup("service", broken_service_close)
    lifetime.add_cleanup("scheduler", lambda: released.append("scheduler"))
    lifetime.close()
    lifetime.close()

    assert released == ["scheduler", "service", "database"]
    assert "service close failed" in caplog.text
