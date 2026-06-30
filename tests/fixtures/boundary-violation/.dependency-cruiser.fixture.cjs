/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'pkg-a-not-to-pkg-b',
      severity: 'error',
      comment: 'Deliberate fixture violation for regression testing',
      from: { path: '^tests/fixtures/boundary-violation/pkg-a/' },
      to: { path: '^tests/fixtures/boundary-violation/pkg-b/' },
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    tsPreCompilationDeps: true,
  },
};
