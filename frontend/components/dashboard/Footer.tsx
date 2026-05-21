"use client";

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer-container">
        <div className="site-footer-logo-col">
          <img src="/wissen_logo.png" alt="Wissen Logo" />
          <p>
            At Wissen Technology, we deliver niche, custom-built products that
            solve complex business challenges across industries worldwide.
          </p>
        </div>

        <div className="site-footer-col">
          <h4>Portal Links</h4>
          <ul>
            <li>
              <Link href="/dashboard">Dashboard Home</Link>
            </li>
            <li>
              <Link href="/dashboard/jd-generator">JD Generator</Link>
            </li>
            <li>
              <Link href="/dashboard/sourcing">Sourcing Module</Link>
            </li>
          </ul>
        </div>

        <div className="site-footer-col">
          <h4>Wissen Corporate</h4>
          <ul>
            <li>
              <a href="https://www.wissen.com" target="_blank" rel="noreferrer">
                Corporate Website
              </a>
            </li>
            <li>
              <a
                href="https://www.linkedin.com/company/wissen-technology"
                target="_blank"
                rel="noreferrer"
              >
                LinkedIn Page
              </a>
            </li>
            <li>
              <a
                href="https://www.wissen.com/careers"
                target="_blank"
                rel="noreferrer"
              >
                Careers Opportunities
              </a>
            </li>
          </ul>
        </div>

        <div className="site-footer-col">
          <h4>Key Locations</h4>
          <p>
            United States <br />
            United Kingdom <br />
            United Arab Emirates <br />
            India (Bengaluru, Mumbai) <br />
            Australia
          </p>
        </div>
      </div>

      <div className="site-footer-bottom">
        <p className="site-footer-copyright">
          &copy; {new Date().getFullYear()} Wissen Technology. All rights
          reserved.
        </p>
        <div className="site-footer-links">
          <a
            href="https://www.wissen.com/privacy-policy"
            target="_blank"
            rel="noreferrer"
            className="site-footer-link"
          >
            Privacy Policy
          </a>
          <a
            href="https://www.wissen.com/terms-of-use"
            target="_blank"
            rel="noreferrer"
            className="site-footer-link"
          >
            Terms of Use
          </a>
        </div>
      </div>
    </footer>
  );
}
