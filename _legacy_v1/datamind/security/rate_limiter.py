class RateLimiter:
    _buckets: dict = {}
    
    @classmethod
    def check(cls, key: str, max_requests: int, window_seconds: int) -> dict:
        import time
        now = time.time()
        
        if key not in cls._buckets:
            cls._buckets[key] = {"count": 0, "window_start": now}
        
        bucket = cls._buckets[key]
        
        if now - bucket["window_start"] > window_seconds:
            bucket["count"] = 0
            bucket["window_start"] = now
        
        bucket["count"] += 1
        
        if bucket["count"] > max_requests:
            remaining = window_seconds - (now - bucket["window_start"])
            return {
                "allowed": False,
                "retry_after_seconds": int(remaining),
                "message": f"Too many requests. Please wait {int(remaining)} seconds."
            }
        
        return {"allowed": True}

    @classmethod
    def check_login(cls, email: str) -> dict:
        return cls.check(f"login:{email}", max_requests=5, window_seconds=60)

    @classmethod
    def check_register(cls, ip_hint: str) -> dict:
        return cls.check(f"register:{ip_hint}", max_requests=3, window_seconds=300)

    @classmethod
    def check_chat(cls, user_id: int) -> dict:
        return cls.check(f"chat:{user_id}", max_requests=30, window_seconds=60)

    @classmethod
    def check_file_upload(cls, user_id: int) -> dict:
        return cls.check(f"upload:{user_id}", max_requests=10, window_seconds=300)

    @classmethod
    def check_ollama(cls, user_id: int) -> dict:
        return cls.check(f"ollama:{user_id}", max_requests=20, window_seconds=60)
