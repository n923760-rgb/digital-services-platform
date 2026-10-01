# Trusted administrative proxy identity

Caddy reaches the API through the dedicated internal admin_proxy network using the api-proxy alias. The API trusts forwarded identity only from Caddy's fixed TRUSTED_PROXY_IP and its own loopback; other containers' direct requests cannot select a client address through X-Forwarded-For. Caddy retains its default rejection of untrusted incoming forwarded headers. No wildcard forwarded trust is used.

PROXY_NETWORK_SUBNET defaults to 172.30.0.0/29 and TRUSTED_PROXY_IP to 172.30.0.2. For another deployment, choose a non-overlapping subnet and distinct free proxy/API addresses inside it together. API_PROXY_IP defaults to 172.30.0.3, preventing dynamic allocation from taking Caddy's reserved address. Only Caddy and API join this trust network; backend services remain on the normal network. This is repository configuration, not a production network migration or launch.

Compose CI runs proxy_smoke from two independent containers. Each uses the same unknown test username, verifies its own Redis login counter after a request through Caddy and a direct API request, and supplies spoofed forwarded headers in both paths. The smoke refuses execution without CI_PROXY_TEST=1 and is for disposable deployments only. It does not create an admin or authenticate a customer.

A real external HTTPS/domain deployment still needs provider/firewall configuration and staging verification. The existing login limiter is source+username scoped; atomic source/account-wide protection is the next independent DSP-007 task.
