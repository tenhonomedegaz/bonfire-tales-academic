// import { registerProviders, registeredProviders } from './providers';
import { registerRepositories, registeredRepositories } from './repositories';

const registeredDependencies = {
  ...registeredRepositories,
  // ...registeredProviders,
};

function registerDependencies(): void {
  registerRepositories();
  // registerProviders();
}

export { registeredDependencies, registerDependencies };
