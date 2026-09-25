const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.BS4_X_Bb.js",app:"_app/immutable/entry/app.DoaqChka.js",imports:["_app/immutable/entry/start.BS4_X_Bb.js","_app/immutable/chunks/CTXhSrQn.js","_app/immutable/chunks/WS1bLMZz.js","_app/immutable/chunks/Bao9V6Rl.js","_app/immutable/entry/app.DoaqChka.js","_app/immutable/chunks/WS1bLMZz.js","_app/immutable/chunks/Bao9V6Rl.js","_app/immutable/chunks/Bocc91eC.js","_app/immutable/chunks/C5-g0Q-M.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./chunks/0-CEJCdOfz.js')),
			__memo(() => import('./chunks/1-QVO2-ZXK.js')),
			__memo(() => import('./chunks/2-CaEpGcoe.js').then(function (n) { return n.a3; }))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/[...catchall]",
				pattern: /^(?:\/([^]*))?\/?$/,
				params: [{"name":"catchall","optional":false,"rest":true,"chained":true}],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();

const prerendered = new Set([]);

const base = "";

export { base, manifest, prerendered };
//# sourceMappingURL=manifest.js.map
