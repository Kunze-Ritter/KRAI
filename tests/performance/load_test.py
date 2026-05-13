# Locust load test for HTTP API endpoints
from locust import HttpUser, between, task


class ApiUser(HttpUser):
    wait_time = between(1, 3)

    @task(2)
    def get_products(self):
        self.client.get("/api/v1/products")

    @task(1)
    def create_product(self):
        payload = {
            "name": "LoadTest Product",
            "type": "printer",
            "manufacturer_id": 1,
        }
        self.client.post("/api/v1/products", json=payload)
