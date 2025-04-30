import { test } from '@playwright/test';
import { execSync } from 'child_process';

test('Run the Python link checker script', async () => {
  const url = 'https://example.com'; // Replace with any test URL
  const output = execSync(`python3 webcrawler.py --url ${url}`, { encoding: 'utf-8' });
  console.log(output);
});