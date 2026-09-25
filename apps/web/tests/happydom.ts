/**
 * Test-environment bootstrap: registers happy-dom globals (document,
 * window, …). Imported FIRST in every *.test.tsx so it evaluates before
 * @testing-library modules capture the global document.
 */
import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register();
