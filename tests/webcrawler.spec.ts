import { test } from '@playwright/test';
import { execSync } from 'child_process';

test('Run the Python link checker script', async () => {
  const url = 'https://example.com'; // Replace with any test URL

  // Uncomment and customize these lines to pass flags dynamically via environment variables:
  // const followFlag = process.env.FOLLOW === 'true' ? '--follow' : '';
  // const failFlag = process.env.FAIL_ON_BROKEN === 'true' ? '--fail-on-broken' : '';
  // const cmd = `python3 webcrawler.py --url ${url} ${followFlag} ${failFlag}`.trim();

  // Or just run without flags for now:
  const cmd = `python3 webcrawler.py --url ${url}`;

  const output = execSync(cmd, { encoding: 'utf-8' });
  console.log(output);
});