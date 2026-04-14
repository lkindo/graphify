package com.example

import java.util.List
import java.util.ArrayList

class HttpClient {
    String baseUrl
    int timeout

    HttpClient(String baseUrl, int timeout) {
        this.baseUrl = baseUrl
        this.timeout = timeout
    }

    String get(String path) {
        return "${baseUrl}${path}"
    }

    String post(String path, String body) {
        return "${baseUrl}${path}"
    }
}

interface Processor {
    String process(String input)
}

enum Status {
    ACTIVE, INACTIVE, PENDING
}

HttpClient createClient(String url) {
    return new HttpClient(url, 30)
}
