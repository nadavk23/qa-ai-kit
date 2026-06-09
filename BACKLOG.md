# QA AI Kit — Feature Backlog

**Last Updated:** 2026-06-06  
**Total Features:** 30+ (Planned)  
**In Progress:** Phase 1  
**Completed:** Web, Mobile (iOS/Android), Device Management, YAML Runner, API (REST)

---

## Phase 1: API & CLI Expansion (Current Sprint)

### Phase 1.1: Advanced API Testing
- [ ] **GraphQL Queries & Mutations**
  - `act({ action: "graphql", query: "{ users { id name } }" })`
  - Support variables, aliases, fragments
  - Error handling & response validation
  - Estimated: 8h
  - Related: `api_request` tool

- [ ] **WebSocket Testing**
  - `act({ action: "ws_connect", url: "ws://..." })`
  - `act({ action: "ws_send", message: {...} })`
  - `assert({ type: "ws_message", contains: "..." })`
  - Connection lifecycle, reconnection logic
  - Estimated: 10h
  - Related: `api_request`, `session`

- [ ] **gRPC Testing**
  - gRPC client with proto schema discovery
  - `act({ action: "grpc_call", service: "...", method: "...", data: {...} })`
  - Streaming support (client, server, bidi)
  - Estimated: 12h
  - Related: `api_request`

### Phase 1.2: Terminal/CLI Testing
- [ ] **CLI Platform Support**
  - `platform: "terminal"` detection in YAML
  - `device_allocate({ platform: "terminal", command: "/bin/bash" })`
  - Estimated: 6h
  - Related: `device_allocate`, new `terminal_runner.py`

- [ ] **Terminal Interactions**
  - `act({ action: "input", text: "command\n" })`
  - `act({ action: "press", key: "Enter" })`
  - `assert({ type: "visible", text: "output" })`
  - Estimated: 8h
  - Related: node-pty integration

- [ ] **Terminal Session Management**
  - Multi-session support for pipe chains
  - `session({ action: "switch", sessionId: "..." })`
  - Estimated: 4h

### Phase 1.3: Network Cassettes (Record/Replay)
- [ ] **Cassette Storage & Indexing**
  - Content-addressed HAR format (.argus/cassette-store/)
  - Manifest per test (per-platform)
  - Estimated: 10h
  - Related: `yaml_runner.py`, new `cassette.py`

- [ ] **Record Mode**
  - Capture all HTTP/WebSocket traffic
  - Automatic request/response deduping
  - Estimated: 8h

- [ ] **Replay Mode**
  - Deterministic matching (URL canonicalization, body)
  - Cassette miss handling (strict/lenient/record-on-miss)
  - Estimated: 8h

- [ ] **Cassette CLI Tools**
  - `argus cassette show <manifest>` → flat HAR
  - `argus cassette lint [path]` → secret scanning
  - `argus cassette prune` → GC orphans
  - Estimated: 6h

---

## Phase 2: Test Authoring & Debugging (Month 2)

### Phase 2.1: Record-flow (Auto-YAML Generation)
- [ ] **Web Recording**
  - DOM event listeners (click, input, key, scroll)
  - Selector priority (data-testid > aria-label > CSS path)
  - Paired cassette auto-generation
  - Estimated: 12h

- [ ] **Mobile Recording**
  - UIKit swizzles (iOS), UiAutomator2 (Android)
  - Accessibility ID priority
  - Estimated: 14h

- [ ] **Record-flow CLI**
  - `argus record-flow --platform web --url http://localhost:3000 --output tests/login.yaml`
  - Driver selection (playwright, cdp, extension)
  - Estimated: 6h

### Phase 2.2: Visual Regression
- [ ] **Screenshot Baselines**
  - Store snapshots per platform/device/locale
  - Delta comparison (pixel-level, perceptual)
  - Estimated: 8h

- [ ] **Baseline Management**
  - Auto-approve in CI (with review gate)
  - `argus baseline approve <test>`
  - Estimated: 6h

- [ ] **Visual Assert Tool**
  - `assert({ type: "visual", baseline: "login-form", threshold: 0.95 })`
  - Estimated: 4h

### Phase 2.3: Element Annotation & Debugging
- [ ] **Element Overlay**
  - Numbered bounding boxes on inspect
  - `inspect({ annotateElements: true })`
  - Estimated: 4h

- [ ] **Annotation Drawing**
  - Draw arrows, rectangles, text on screenshots
  - `act({ action: "annotate", shapes: [...] })`
  - Estimated: 6h

### Phase 2.4: Video Recording
- [ ] **Video Capture** (Web & Mobile)
  - Opt-in via `recordVideo: true` or CLI flag
  - H.264 codec, 30fps
  - Estimated: 10h

- [ ] **Video Artifacts in CI**
  - Auto-upload on failure
  - Estimated: 4h

---

## Phase 3: Platform Expansion (Month 3)

### Phase 3.1: Chrome Extension Testing
- [ ] **Extension Loading**
  - Load unpacked Manifest V3 extensions
  - `inspect({ extensionPath: "..." })`
  - Estimated: 8h

- [ ] **Popup/Options/Content Script Testing**
  - Navigate between extension pages
  - Test content script injection
  - Estimated: 8h

- [ ] **Service Worker Logging**
  - Capture SW console logs
  - Estimated: 4h

### Phase 3.2: macOS Testing
- [ ] **Accessibility API Driver**
  - Read UI tree via AXUIElementCreateSystemWide
  - Estimated: 12h

- [ ] **AppleScript Fallback**
  - Keystroke, click, mouse position
  - Estimated: 6h

- [ ] **In-Process Shim (Optional)**
  - DYLD injection for µs-scale operations
  - Estimated: 20h (complex)

### Phase 3.3: watchOS Testing
- [ ] **WatchDriver**
  - Digital Crown rotation
  - Tap, swipe, force touch
  - Estimated: 10h

- [ ] **Paired iPhone/Watch Testing**
  - Multi-device orchestration
  - Estimated: 8h

---

## Phase 4: QA Specialization (Month 4+)

### Phase 4.1: AI Vision Assertions
- [ ] **AI Vision Model Integration**
  - `assert({ type: "ai", prompt: "Login form is visible and correct" })`
  - Screenshot → Claude vision → pass/fail
  - Estimated: 6h

- [ ] **Drift Detection**
  - Compare against baseline + AI annotation
  - Estimated: 8h

### Phase 4.2: Accessibility Auditing
- [ ] **WCAG 2.1 AA Scanner**
  - Axe-core integration (web)
  - Color contrast, ARIA roles, keyboard nav
  - Estimated: 8h

### Phase 4.3: Performance Testing
- [ ] **Core Web Vitals**
  - FCP, LCP, CLS, FID capture
  - Pass/fail thresholds
  - Estimated: 6h

- [ ] **Mobile Performance**
  - Frame rate (60 FPS / 120 FPS)
  - Memory profiling
  - Estimated: 10h

### Phase 4.4: Agent Mode & QA Agent
- [ ] **Autonomous Agent Testing**
  - Strategic test planning
  - Risk-based coverage
  - Estimated: 20h

- [ ] **QA Agent (Persistent Knowledge)**
  - Product understanding across runs
  - Coverage tracking
  - Estimated: 16h

---

## Phase 5: Advanced/Enterprise (Month 5+)

### Phase 5.1: Shim Drivers (In-Process)
- [ ] **iOS Shim (DYLD Injection)**
  - URLSessionConfiguration swizzle
  - UIKit event capture
  - Estimated: 20h

- [ ] **Android Shim (Frida)**
  - Frida agent injection
  - Cert pinning bypass
  - Estimated: 18h

- [ ] **macOS Shim (Objective-C)**
  - AppKit method swizzling
  - Estimated: 16h

### Phase 5.2: Cloud Device Routing
- [ ] **Real Device Orchestration**
  - LambdaTest / BrowserStack integration
  - Device pool management
  - Estimated: 16h

### Phase 5.3: CI/CD Orchestration
- [ ] **Nightly Cassette Updates**
  - Auto-PR for cassette drift
  - Estimated: 8h

- [ ] **Multi-Platform Matrix**
  - Parallel web (6 browsers) + mobile (5 devices)
  - Estimated: 6h

---

## Backlog (Unscheduled)

- [ ] Custom HTTP auth providers (OAuth, mTLS, etc.)
- [ ] HAR import from Charles/Burp
- [ ] Synthetic user journey tracking
- [ ] Test flake analysis & quarantine
- [ ] Performance regression detection
- [ ] Compliance audit mode (PCI, HIPAA, etc.)
- [ ] Multi-locale testing automation
- [ ] Pixel-perfect visual regression (OpenCV)
- [ ] Shadow DOM & cross-origin iframe support
- [ ] Keyboard accessibility auto-scan

---

## Effort Estimate

| Phase | Features | Est. Hours | Timeline |
|-------|----------|-----------|----------|
| **Phase 1** | GraphQL, WebSocket, gRPC, CLI, Cassettes | 80h | 2 weeks |
| **Phase 2** | Record-flow, Visual Regression, Video | 60h | 2 weeks |
| **Phase 3** | Chrome Ext, macOS, watchOS | 70h | 2-3 weeks |
| **Phase 4** | AI Vision, A11y, Perf, Agent | 60h | 2-3 weeks |
| **Phase 5** | Shims, Cloud, Orchestration | 70h | 3+ weeks |
| **Total** | | **340h** | **12-16 weeks** |

---

## Success Metrics

- ✅ Phase 1: All API platforms + CLI + cassettes working end-to-end
- ✅ Phase 2: Agents can auto-record new tests without YAML authoring
- ✅ Phase 3: Desktop & wearable app testing parity with mobile
- ✅ Phase 4: AI-assisted bug detection + compliance audits
- ✅ Phase 5: Enterprise-scale cloud testing + real devices

---

## How to Contribute

Pick a feature from the backlog, create a branch `feature/<name>`, and submit a PR with:
- Tests (unit + integration)
- Documentation (README + inline)
- Example YAML/code snippets
- Effort estimate (actual vs. planned)

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.
