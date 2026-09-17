module.exports = {
    testEnvironment: "node",
    testTimeout: 30000,
    testMatch: ["**/tests/**/*.test.ts"],
    testPathIgnorePatterns: ["/node_modules/"],
    clearMocks: true,
    setupFiles: ["<rootDir>/tests/setup.ts"],
    // babel-jest only strips TypeScript syntax, so it never calls the compiler
    // API and does not care which TypeScript version the repo has installed.
    transform: {
        "^.+\\.[tj]sx?$": [
            "babel-jest",
            {
                presets: [
                    ["@babel/preset-env", { targets: { node: "current" } }],
                    "@babel/preset-typescript",
                ],
            },
        ],
    },
};
