"""Tầng integration: 4 service Docker phải sống. SKIP khi `make up` chưa chạy."""

from scripts.healthcheck import health_urls, ping


def test_all_services_respond(require_services):
    require_services()  # skip nếu thiếu bất kỳ service nào
    for name, url in health_urls().items():
        assert ping(url), f"{name} không phản hồi tại {url}"
