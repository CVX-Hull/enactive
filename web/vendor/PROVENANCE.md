# Vendored browser libraries

These files are served as-is by the spectator page. The page has no build step and loads
nothing from a network origin at run time (the control path's Content-Security-Policy is
`default-src 'self'`). Each package was fetched with `npm pack <name>@<version>` from
`https://registry.npmjs.org/` on 2026-11-06; the tarball digests match the registry's
`dist.integrity` where listed. Files carry the `.js` extension so every static server
sends a JavaScript media type for module scripts.

| Library | Version | License | Tarball | Tarball SHA-256 |
| --- | --- | --- | --- | --- |
| Preact | 11.2.0 | MIT | https://registry.npmjs.org/preact/-/preact-11.2.0.tgz (`sha512-/HfHI/7N84e6GrWBJ3J280z3mLaRJiDcSvj/A+y/4AbLnND/1UlGHe1sR6oYuTGwId0nP7dqDU9OnLxMPZ7xBg==`) | `3c4456766bd32b6b534d52bf4e9c2a29b33e7eedf6e96ed479300ba1a7888ebf` |
| htm | 3.1.1 | Apache-2.0 | https://registry.npmjs.org/htm/-/htm-3.1.1.tgz (`sha512-983Vyg8NwUE7JkZ6NmOqpCZ+sh1bKv2iYTlUkzlWmA5JD2acKoxd4KVxbMmxX/85mtfdnDmTFoNKcg5DGAvxNQ==`) | `2425b9bee11409177bcabc7f32e319926fc6690c1701c0b257c88bdff2d5ba90` |
| Apache ECharts | 5.5.1 | Apache-2.0 | https://registry.npmjs.org/echarts/-/echarts-5.5.1.tgz (`sha512-Fce8upazaAXUVUVsjgV6mBnGuqgO+JNDlcgF79Dksy4+wgGpQB2lmYoO4TSweFg/mZITdpGHomw/cNBJZj1icA==`) | `1f0eae29c406496a77789a7d7f56b811cae034ac95c0b3808215998f4ba0fbf3` |

## Files

| Published file | Source in the tarball | Changed | SHA-256 of the file |
| --- | --- | --- | --- |
| `preact.js` | `dist/preact.mjs` | no | `bdcbd9abdf2c77c5c45326eab42191e949222d479d0d5f69467387a77040cb55` |
| `hooks.js` | `hooks/dist/hooks.mjs` | one specifier (below) | `5f732f493f1fdc7a6c20f18950ebab9e6657d38876f5f1dca33d05bf6f029dd2` |
| `htm.js` | `dist/htm.mjs` | no | `ab33dd3f38059b9be4d5f5350128eefb2356639c4e0bbe9d9e8b3ba75847e9e4` |
| `echarts.js` | `dist/echarts.esm.min.mjs` | no | `342d276d87314bfd6af8c4dd48b5cbbf8cb556642aa8a770d740057dbc996588` |
| `LICENSE-preact`, `LICENSE-htm`, `LICENSE-echarts`, `NOTICE-echarts` | `LICENSE`, `NOTICE` | no | see `shasum -a 256` |

**The one change.** Browsers resolve bare specifiers only through an import map, and an
inline import map is blocked by the page's Content-Security-Policy. So `hooks.js` is the
upstream `hooks/dist/hooks.mjs` (SHA-256
`e862ab2973aa6455eaa0f77c5d832d2157d6be59a17c8ba546550a575b58c6b4`) with its single
import specifier rewritten:

```
sed 's/from"preact"/from".\/preact.js"/' hooks/dist/hooks.mjs > web/vendor/hooks.js
```

The files end with `sourceMappingURL` comments for maps that are not vendored; browsers
fetch them only when developer tools are open.

## Upgrading

Fetch the new tarball, replace the files above, repeat the one `sed` for `hooks.js`,
update this table and the versions in `NOTICE.md`, and run `node tests/test_viewer.cjs`.
