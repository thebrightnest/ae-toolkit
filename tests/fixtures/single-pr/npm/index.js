const fs = require('fs');
const isNumber = require('is-number');

const taskId = process.env.AET_TASK_ID || 'task';
const value = 7;
const line = `${taskId}: is-number(${value})=${isNumber(value)}\n`;

// Append to the shared marker so the second task can prove it started from
// the live tip of the integration branch.
fs.writeFileSync('marker.txt', line, { flag: 'a' });
console.log(line.trim());
