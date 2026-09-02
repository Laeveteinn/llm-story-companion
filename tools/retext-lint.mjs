import fs from 'node:fs/promises'
import {unified} from 'unified'
import retextEnglish from 'retext-english'
import retextStringify from 'retext-stringify'
import retextRepeatedWords from 'retext-repeated-words'
import retextIndefiniteArticle from 'retext-indefinite-article'
import retextRedundantAcronyms from 'retext-redundant-acronyms'
import retextContractions from 'retext-contractions'
import retextPassive from 'retext-passive'
import retextIntensify from 'retext-intensify'

const path = process.argv[2]
if (!path) {
  console.error('usage: node tools/retext-lint.mjs <file>')
  process.exit(2)
}
const text = await fs.readFile(path, 'utf8')
const file = await unified()
  .use(retextEnglish)
  .use(retextRepeatedWords)
  .use(retextIndefiniteArticle)
  .use(retextRedundantAcronyms)
  .use(retextContractions)
  .use(retextPassive)
  .use(retextIntensify)
  .use(retextStringify)
  .process({value: text, path})

const out = file.messages.map((m) => ({
  source: m.source ?? null,
  ruleId: m.ruleId ?? null,
  message: m.reason ?? m.message ?? String(m),
  line: m.place?.start?.line ?? null,
  column: m.place?.start?.column ?? null,
  endLine: m.place?.end?.line ?? null,
  endColumn: m.place?.end?.column ?? null,
  actual: m.actual ?? null,
  expected: m.expected ?? null,
  fatal: m.fatal ?? false
}))
console.log(JSON.stringify(out))
process.exit(out.length ? 1 : 0)
