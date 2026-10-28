// GitHub heading IDs have one maintained implementation; Python owns parsing.
import GithubSlugger from 'github-slugger';
import { readFileSync } from 'node:fs';

const documents = JSON.parse(readFileSync(0, 'utf8'));
const anchors = documents.map(headings => {
  const slugger = new GithubSlugger();
  return headings.map(heading => slugger.slug(heading));
});
process.stdout.write(JSON.stringify(anchors));
