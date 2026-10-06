(() => {
  const reportName = "__complianceStorageViolations";
  const report = (api, operation) => {
    const current = window[reportName] || [];
    current.push({
      path: `browser:${api}`,
      type: operation,
    });
    Object.defineProperty(window, reportName, {
      configurable: true,
      value: current,
      writable: true,
    });
  };

  const findDescriptor = (target, property) => {
    for (let prototype = target; prototype; prototype = Object.getPrototypeOf(prototype)) {
      const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
      if (descriptor) return descriptor;
    }
    return undefined;
  };

  const interceptWindowStorage = (property) => {
    const descriptor = findDescriptor(window, property);
    if (!descriptor || !descriptor.configurable || !descriptor.get) return;
    Object.defineProperty(window, property, {
      configurable: true,
      get() {
        report(property, "browser_storage_access");
        return Reflect.apply(descriptor.get, this, []);
      },
    });
  };

  for (const property of ["localStorage", "sessionStorage", "indexedDB", "caches"]) {
    interceptWindowStorage(property);
  }

  const navigatorDescriptor = findDescriptor(navigator, "serviceWorker");
  if (navigatorDescriptor?.configurable && navigatorDescriptor.get) {
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      get() {
        const serviceWorker = Reflect.apply(navigatorDescriptor.get, this, []);
        if (serviceWorker && typeof serviceWorker.register === "function") {
          const originalRegister = serviceWorker.register.bind(serviceWorker);
          serviceWorker.register = (...args) => {
            report("serviceWorker", "service_worker_registration");
            return originalRegister(...args);
          };
        }
        return serviceWorker;
      },
    });
  }

  Object.defineProperty(window, reportName, {
    configurable: true,
    value: [],
    writable: true,
  });
})();
