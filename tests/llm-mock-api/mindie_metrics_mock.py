#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer


METRICS_BODY = """# HELP request_received_total Count of received requests.
# TYPE request_received_total counter
request_received_total{model_name="Qwen3-8B"} 0
# HELP request_success_total Count of successfully processed requests.
# TYPE request_success_total counter
request_success_total{model_name="Qwen3-8B"} 0
# HELP request_failed_total Count of failed requests.
# TYPE request_failed_total counter
request_failed_total{model_name="Qwen3-8B"} 0
# HELP prompt_tokens_total Number of prefill tokens processed.
# TYPE prompt_tokens_total counter
prompt_tokens_total{model_name="Qwen3-8B"} 0
# HELP generation_tokens_total Number of generation tokens processed.
# TYPE generation_tokens_total counter
generation_tokens_total{model_name="Qwen3-8B"} 0
# HELP num_preemptions_total Cumulative number of preemption from the engine.
# TYPE num_preemptions_total counter
num_preemptions_total{model_name="Qwen3-8B"} 0
# HELP num_requests_running Number of requests currently running on GPU.
# TYPE num_requests_running gauge
num_requests_running{model_name="Qwen3-8B"} 20
# HELP num_requests_waiting Number of requests waiting to be processed.
# TYPE num_requests_waiting gauge
num_requests_waiting{model_name="Qwen3-8B"} 10
# HELP num_requests_swapped Number of requests swapped to CPU.
# TYPE num_requests_swapped gauge
num_requests_swapped{model_name="Qwen3-8B"} 0
# HELP avg_prompt_throughput_toks_per_s Average prefill throughput in tokens/s.
# TYPE avg_prompt_throughput_toks_per_s gauge
avg_prompt_throughput_toks_per_s{model_name="Qwen3-8B"} 0
# HELP avg_generation_throughput_toks_per_s Average generation throughput in tokens/s.
# TYPE avg_generation_throughput_toks_per_s gauge
avg_generation_throughput_toks_per_s{model_name="Qwen3-8B"} 0
# HELP failed_request_perc Requests failure rate. 1 means 100 percent usage.
# TYPE failed_request_perc gauge
failed_request_perc{model_name="Qwen3-8B"} 0
# HELP npu_cache_usage_perc NPU KV-cache usage. 1 means 100 percent usage.
# TYPE npu_cache_usage_perc gauge
npu_cache_usage_perc{model_name="Qwen3-8B"} 30
# HELP cpu_cache_usage_perc CPU KV-cache usage. 1 means 100 percent usage.
# TYPE cpu_cache_usage_perc gauge
cpu_cache_usage_perc{model_name="Qwen3-8B"} 0
# HELP npu_prefix_cache_hit_rate NPU prefix cache block hit rate..
# TYPE npu_prefix_cache_hit_rate gauge
npu_prefix_cache_hit_rate{model_name="Qwen3-8B"} 0
# HELP time_to_first_token_seconds Histogram of time to first token in seconds.
# TYPE time_to_first_token_seconds histogram
time_to_first_token_seconds_count{model_name="Qwen3-8B"} 0
time_to_first_token_seconds_sum{model_name="Qwen3-8B"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.001"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.005"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.01"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.02"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.04"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.06"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.08"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.1"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.25"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.5"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="0.75"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="1"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="2.5"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="5"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="7.5"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="10"} 0
time_to_first_token_seconds_bucket{model_name="Qwen3-8B",le="+Inf"} 0
# HELP time_per_output_token_seconds Histogram of time per output token in seconds.
# TYPE time_per_output_token_seconds histogram
time_per_output_token_seconds_count{model_name="Qwen3-8B"} 0
time_per_output_token_seconds_sum{model_name="Qwen3-8B"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.01"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.025"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.05"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.075"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.1"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.15"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.2"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.3"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.4"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.5"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="0.75"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="1"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="2.5"} 0
time_per_output_token_seconds_bucket{model_name="Qwen3-8B",le="+Inf"} 0
# HELP e2e_request_latency_seconds Histogram of end to end request latency in seconds.
# TYPE e2e_request_latency_seconds histogram
e2e_request_latency_seconds_count{model_name="Qwen3-8B"} 0
e2e_request_latency_seconds_sum{model_name="Qwen3-8B"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="1"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="2.5"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="5"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="10"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="15"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="20"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="30"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="40"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="50"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="60"} 0
e2e_request_latency_seconds_bucket{model_name="Qwen3-8B",le="+Inf"} 0
# HELP request_prompt_tokens Number of prefill tokens processed.
# TYPE request_prompt_tokens histogram
request_prompt_tokens_count{model_name="Qwen3-8B"} 0
request_prompt_tokens_sum{model_name="Qwen3-8B"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="10"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="50"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="100"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="200"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="500"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="1000"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="2000"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="5000"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="10000"} 0
request_prompt_tokens_bucket{model_name="Qwen3-8B",le="+Inf"} 0
# HELP request_generation_tokens Number of generation tokens processed.
# TYPE request_generation_tokens histogram
request_generation_tokens_count{model_name="Qwen3-8B"} 0
request_generation_tokens_sum{model_name="Qwen3-8B"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="10"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="50"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="100"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="200"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="500"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="1000"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="2000"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="5000"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="10000"} 0
request_generation_tokens_bucket{model_name="Qwen3-8B",le="+Inf"} 0
"""


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = METRICS_BODY.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Not Found\n")

    def log_message(self, format, *args):
        # Keep output clean for temporary usage.
        return


def main():
    host = "0.0.0.0"
    port = 5001
    server = HTTPServer((host, port), MetricsHandler)
    print(f"Serving mock metrics at http://{host}:{port}/metrics")
    server.serve_forever()


if __name__ == "__main__":
    main()
