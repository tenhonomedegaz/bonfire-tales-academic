const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 1. Fetch traits from django using check_human_traits.py modified
// Or we can just use python to extract them and write them to a JSON file first.
// Let's do that! We'll read from a JSON file.
