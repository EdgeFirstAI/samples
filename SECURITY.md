# Security Policy

## Supported Versions

We release patches for security vulnerabilities based on the following support schedule:

| Version | Support Status |
|---------|---------------|
| main    | ✅ Full support - latest development version |
| < 1.0   | ⚠️ Development - no guarantees, use at your own risk |

Once version 1.0 is released, we will maintain security updates for stable releases according to our versioning policy.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Au-Zone Technologies takes the security of our software seriously. If you believe you have found a security vulnerability in the EdgeFirst Samples repository, please report it to us as described below.

### How to Report a Security Vulnerability

**Email:** support@au-zone.com

**Subject:** "Security Vulnerability - EdgeFirst Samples"

**Please include the following information:**

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- **Full paths of source file(s)** related to the manifestation of the issue
- **The location of the affected source code** (tag/branch/commit or direct URL)
- **Any special configuration required** to reproduce the issue
- **Step-by-step instructions to reproduce the issue**
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit it
- **Suggested fix or mitigation** (if any)

This information will help us triage your report more quickly.

### Response Timeline

- **Acknowledgment:** We will acknowledge receipt of your vulnerability report within **48 hours**
- **Initial Assessment:** We will provide an initial assessment of the issue within **7 days**
- **Fix Timeline:**
  - **Critical vulnerabilities:** Patch within **7 days**
  - **High severity:** Patch within **30 days**
  - **Medium severity:** Fix in next minor release
  - **Low severity:** Fix in next major release

We will keep you informed about the progress toward a fix and full announcement, and may ask for additional information or guidance.

### Responsible Disclosure

We kindly ask that you:

- **Allow reasonable time** for us to investigate and fix the vulnerability before public disclosure
- **Avoid public disclosure** of the vulnerability until we have released a patch
- **Do not exploit the vulnerability** beyond what is necessary to demonstrate it
- **Do not access, modify, or delete data** that does not belong to you
- **Make a good faith effort** to avoid privacy violations, destruction of data, and interruption or degradation of our services

### Recognition

We value the security research community and believe in recognizing researchers who help us maintain the security of our software:

- We will credit you in our security advisories (unless you prefer to remain anonymous)
- We will acknowledge your contribution in release notes
- For significant discoveries, we may provide additional recognition on our website or blog

### Security Update Process

When a security vulnerability is confirmed:

1. **Private Fix:** We will develop a fix in a private repository
2. **Security Advisory:** We will publish a GitHub Security Advisory (when available)
3. **Patch Release:** We will release a patched version
4. **Public Disclosure:** We will publicly disclose the vulnerability details after the patch is available
5. **EdgeFirst Studio Notification:** For vulnerabilities affecting EdgeFirst Studio integration, we will notify users through the platform

### Security Best Practices for Users

When using EdgeFirst Samples in your projects:

- **Keep dependencies updated:** Regularly update to the latest version to receive security patches
- **Review the SBOM:** Check the Software Bill of Materials (sbom.json) for known vulnerabilities in dependencies
- **Secure your deployment:** Follow security best practices for your target platform (embedded Linux, etc.)
- **Validate inputs:** Always validate and sanitize data from external sources (cameras, sensors, network)
- **Use secure communication:** Enable encryption for Zenoh communication in production environments
- **Principle of least privilege:** Run processes with minimal required permissions
- **Monitor for updates:** Watch this repository for security advisories and updates

### Additional Security Services

For organizations requiring enhanced security support, Au-Zone Technologies offers commercial services:

- **Security Audits:** Professional security assessment of your EdgeFirst integration
- **Priority Patches:** Expedited security updates for critical deployments
- **Custom Security Hardening:** Tailored security configurations for your platform
- **Secure Development Training:** Training for your team on secure edge AI development
- **Compliance Consulting:** Assistance with regulatory compliance (automotive, medical, etc.)

**Contact:** support@au-zone.com for commercial security services

---

## Security Features

### Current Security Measures

This repository implements the following security practices:

- **SBOM Generation:** Automated Software Bill of Materials for dependency tracking
- **License Compliance:** Strict license policy enforcement to prevent licensing vulnerabilities
- **Code Quality:** SonarQube integration for static code analysis
- **Dependency Scanning:** Regular dependency audits for known vulnerabilities

### Planned Security Enhancements

Future releases will include:

- Automated dependency vulnerability scanning (Dependabot/Snyk)
- Signed releases with checksums
- Security-focused CI/CD checks
- Container image scanning (when applicable)

---

## Known Limitations

### Platform-Specific Considerations

- **Linux-only features:** Some examples use Linux-specific APIs (DMA buffers, pidfd) which may have platform-specific security considerations
- **Hardware access:** Examples accessing camera/sensor hardware require appropriate permissions
- **Network communication:** Zenoh multicast/unicast communication should be secured in production environments

### Development vs. Production

These samples are designed for **development and learning purposes**. Before using in production:

- Review and harden all security configurations
- Implement proper authentication and authorization
- Enable encryption for network communication
- Follow your organization's security policies
- Conduct security testing and threat modeling

---

## Learn More

- **EdgeFirst Documentation:** https://doc.edgefirst.ai/
- **Zenoh Security:** https://zenoh.io/docs/manual/security/
- **Rust Security Guidelines:** https://anssi-fr.github.io/rust-guide/
- **OWASP Embedded Security:** https://owasp.org/www-project-embedded-application-security/

---

**Last Updated:** 2025-11-18  
**Version:** 1.0
