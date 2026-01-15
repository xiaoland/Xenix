# Quick Reference: Documentation Guide

## 📚 All Documentation Files

### Root Level (Monorepo)

```
ARCHITECTURE.md       → System overview & architectural patterns
DEVELOPMENT.md        → Monorepo setup & quick start
DEPLOYMENT.md         → Overall deployment strategy
```

### Frontend Package

```
packages/frontend/ARCHITECTURE.md       → Vue 3 patterns & structure
packages/frontend/DEVELOPMENT.md        → Frontend dev setup & coding conventions
packages/frontend/DEPLOYMENT.md         → CDN/OSS deployment procedures
```

### Backend Package

```
packages/backend/ARCHITECTURE.md        → Hono API patterns & structure
packages/backend/DEVELOPMENT.md         → Backend dev setup & testing
packages/backend/DEPLOYMENT.md          → Aliyun FC deployment procedures
```

### Shared Package

```
packages/shared/ARCHITECTURE.md         → Type & schema patterns
packages/shared/DEVELOPMENT.md          → Creating & using Zod schemas
packages/shared/DEPLOYMENT.md           → Versioning & release procedures
```

### ML Backend Package

```
packages/ml-backend/ARCHITECTURE.md     → ML operations & adapter patterns
packages/ml-backend/DEVELOPMENT.md      → Python integration & local testing
packages/ml-backend/DEPLOYMENT.md       → Aliyun FC ML worker deployment
```

---

## 🎯 Quick Navigation

### I want to

**Start developing**
→ Read: [Root DEVELOPMENT.md](../DEVELOPMENT.md)
→ Then: Your package's DEVELOPMENT.md

**Understand the system**
→ Read: [Root ARCHITECTURE.md](../ARCHITECTURE.md)
→ Then: Package-specific ARCHITECTURE.md files

**Deploy to production**
→ Read: [Root DEPLOYMENT.md](../DEPLOYMENT.md)
→ Then: Your package's DEPLOYMENT.md

**Add a new feature**

1. Package DEVELOPMENT.md (for patterns)
2. Package ARCHITECTURE.md (for design)
3. Root ARCHITECTURE.md (for system context)

**Debug a problem**
→ Package DEVELOPMENT.md (troubleshooting section)
→ Package ARCHITECTURE.md (understanding patterns)

**Scale/optimize**
→ Package DEPLOYMENT.md (performance section)
→ Root DEPLOYMENT.md (overall strategy)

---

## 📋 By Role

### Frontend Developer

1. [packages/frontend/DEVELOPMENT.md](../packages/frontend/DEVELOPMENT.md) - Get started
2. [packages/frontend/ARCHITECTURE.md](../packages/frontend/ARCHITECTURE.md) - Learn patterns
3. [packages/frontend/DEPLOYMENT.md](../packages/frontend/DEPLOYMENT.md) - Deploy when ready

### Backend Developer

1. [packages/backend/DEVELOPMENT.md](../packages/backend/DEVELOPMENT.md) - Get started
2. [packages/backend/ARCHITECTURE.md](../packages/backend/ARCHITECTURE.md) - Learn patterns
3. [packages/backend/DEPLOYMENT.md](../packages/backend/DEPLOYMENT.md) - Deploy when ready

### ML Engineer

1. [packages/ml-backend/DEVELOPMENT.md](../packages/ml-backend/DEVELOPMENT.md) - Get started
2. [packages/ml-backend/ARCHITECTURE.md](../packages/ml-backend/ARCHITECTURE.md) - Learn patterns
3. [packages/ml-backend/DEPLOYMENT.md](../packages/ml-backend/DEPLOYMENT.md) - Deploy when ready

### DevOps/SRE

1. [Root DEPLOYMENT.md](../DEPLOYMENT.md) - Overall strategy
2. [packages/backend/DEPLOYMENT.md](../packages/backend/DEPLOYMENT.md) - Backend deployment
3. [packages/frontend/DEPLOYMENT.md](../packages/frontend/DEPLOYMENT.md) - Frontend deployment
4. [packages/ml-backend/DEPLOYMENT.md](../packages/ml-backend/DEPLOYMENT.md) - ML deployment

### Architect/Tech Lead

1. [Root ARCHITECTURE.md](../ARCHITECTURE.md) - System overview
2. All package ARCHITECTURE.md files
3. All DEVELOPMENT.md files (understand processes)
4. All DEPLOYMENT.md files (understand operations)

---

## 🔍 Documentation Index

For comprehensive navigation: [docs/ARCHITECTURE_INDEX.md](./ARCHITECTURE_INDEX.md)

---

## 📊 Documentation Statistics

| Level | Files | Focus |
|-------|-------|-------|
| Root | 3 | Monorepo overview & strategy |
| Frontend | 3 | UI/UX development |
| Backend | 3 | API & services |
| Shared | 3 | Types & validation |
| ML Backend | 3 | ML operations |
| **Total** | **15** | Complete coverage |

---

## 🔗 File Relationships

```
Root DEVELOPMENT.md
    ├── packages/frontend/DEVELOPMENT.md
    ├── packages/backend/DEVELOPMENT.md
    ├── packages/shared/DEVELOPMENT.md
    └── packages/ml-backend/DEVELOPMENT.md

Root DEPLOYMENT.md
    ├── packages/frontend/DEPLOYMENT.md
    ├── packages/backend/DEPLOYMENT.md
    ├── packages/shared/DEPLOYMENT.md
    └── packages/ml-backend/DEPLOYMENT.md

Root ARCHITECTURE.md
    ├── packages/frontend/ARCHITECTURE.md
    ├── packages/backend/ARCHITECTURE.md
    ├── packages/shared/ARCHITECTURE.md
    └── packages/ml-backend/ARCHITECTURE.md
```

---

## ✨ Key Principles

✅ **Organized**: Each package has its own focused documentation
✅ **Discoverable**: Clear navigation from root to packages
✅ **Hierarchical**: Root provides overview, packages provide details
✅ **Referenced**: Cross-links between related files
✅ **Maintained**: Single source of truth per topic
✅ **Scalable**: Easy to add new packages following the pattern

---

## 📞 Support

Need help finding documentation?

- **Quick lookup**: This quick reference guide
- **Full navigation**: [ARCHITECTURE_INDEX.md](./ARCHITECTURE_INDEX.md)
- **Detailed exploration**: [docs/explore-plan/](./explore-plan/)

---

**Last Updated**: January 15, 2026
**Documentation Status**: ✅ Complete (15 files)
**Coverage**: 100% - All packages fully documented
