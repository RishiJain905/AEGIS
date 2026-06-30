/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      comment: 'Circular dependencies are forbidden',
      from: {},
      to: { circular: true },
    },
    {
      name: 'packages-not-to-apps',
      severity: 'error',
      comment: 'Domain packages must not import application entry points',
      from: { path: '^packages/' },
      to: { path: '^apps/' },
    },
    {
      name: 'packages-not-to-services',
      severity: 'error',
      comment: 'Domain packages must not import services',
      from: { path: '^packages/' },
      to: { path: '^services/' },
    },
    {
      name: 'web-not-to-api',
      severity: 'error',
      comment: 'Web app must not import API internals',
      from: { path: '^apps/web/' },
      to: { path: '^apps/api/' },
    },
    {
      name: 'no-private-cross-package',
      severity: 'error',
      comment: 'Do not import private source paths from other packages',
      from: {},
      to: {
        path: '^packages/[^/]+/src/(?!index)',
        pathNot: ['^packages/[^/]+/src/index'],
      },
    },
  ],
  options: {
    doNotFollow: {
      path: 'node_modules',
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: 'tsconfig.base.json',
    },
  },
};
