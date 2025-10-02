# Coding Standards

## Overview

This document establishes comprehensive coding standards for the A Fine Wine Dynasty project to ensure code quality, maintainability, and consistency across all components of our full-stack application.

## Documentation Standards

### JSDoc Requirements

**All public functions, interfaces, classes, and modules MUST include comprehensive JSDoc comments.**

#### Function Documentation

```typescript
/**
 * Calculates prospect performance score based on statistical data and ML predictions
 *
 * @param prospectData - The prospect's statistical data including batting average, OPS, etc.
 * @param predictions - ML model predictions for future performance
 * @param weights - Optional weighting factors for different metrics (defaults to balanced weights)
 * @returns Promise resolving to performance score object with breakdown by category
 *
 * @throws {ValidationError} When prospect data is incomplete or invalid
 * @throws {ModelError} When ML predictions are unavailable or corrupted
 *
 * @example
 * ```typescript
 * const score = await calculatePerformanceScore(
 *   { battingAvg: 0.285, ops: 0.850, fielding: 0.975 },
 *   { projectedWAR: 3.2, confidence: 0.87 }
 * );
 * console.log(score.overall); // 8.5
 * ```
 *
 * @since 1.0.0
 * @version 1.2.0
 */
```

#### Interface Documentation

```typescript
/**
 * Represents a baseball prospect with comprehensive evaluation data
 *
 * @interface ProspectProfile
 * @since 1.0.0
 */
interface ProspectProfile {
  /** Unique identifier for the prospect */
  id: string;

  /**
   * Prospect's full name as registered with MLB
   * @example "Juan Soto"
   */
  name: string;

  /**
   * Current position(s) the prospect plays
   * @example ["OF", "1B"]
   */
  positions: Position[];

  /**
   * Statistical performance data
   * @see {@link StatisticalData} for detailed breakdown
   */
  stats: StatisticalData;
}
```

#### Class Documentation

```typescript
/**
 * Manages prospect evaluation and ranking operations
 *
 * Handles data retrieval, ML predictions, and comparison logic for baseball prospects.
 * Integrates with MLB API and internal ML models to provide comprehensive evaluations.
 *
 * @class ProspectEvaluator
 * @implements {IEvaluator}
 * @since 1.0.0
 *
 * @example
 * ```typescript
 * const evaluator = new ProspectEvaluator({
 *   mlModelVersion: "v2.1",
 *   dataSource: "mlb-api"
 * });
 *
 * const ranking = await evaluator.rankProspects(prospects);
 * ```
 */
```

#### Module Documentation

```typescript
/**
 * @fileoverview Prospect comparison utilities and ML integration
 *
 * This module provides core functionality for comparing baseball prospects using
 * statistical analysis, ML predictions, and historical analog matching.
 *
 * @module ProspectComparison
 * @version 2.0.0
 * @author A Fine Wine Dynasty Team
 * @since 1.0.0
 *
 * @requires {@link ../ml/prediction-engine}
 * @requires {@link ../data/prospect-repository}
 */
```

### Required JSDoc Tags

- `@param` - Parameter description with type information
- `@returns` - Return value description
- `@throws` - Exceptions that may be thrown
- `@example` - Usage examples (required for complex functions)
- `@since` - Version when feature was introduced
- `@deprecated` - Mark deprecated features with replacement info
- `@see` - Cross-references to related functionality
- `@todo` - Known limitations or future improvements

## Code Quality Standards

### TypeScript Standards

#### Type Safety
- **Strict mode enabled**: All TypeScript strict flags must be enabled
- **No `any` types**: Use proper typing or `unknown` with type guards
- **Explicit return types**: All function signatures must declare return types
- **Interface over type**: Prefer interfaces for object shapes

```typescript
// ✅ Good
interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
}

function fetchProspect(id: string): Promise<ApiResponse<ProspectProfile>> {
  // implementation
}

// ❌ Bad
function fetchProspect(id: any): Promise<any> {
  // implementation
}
```

#### Naming Conventions
- **Variables/Functions**: camelCase
- **Interfaces**: PascalCase with descriptive names
- **Types**: PascalCase with `Type` suffix if needed
- **Constants**: SCREAMING_SNAKE_CASE
- **Files**: kebab-case for components, camelCase for utilities

### React/Next.js Standards

#### Component Structure
```typescript
/**
 * Displays prospect comparison data with interactive radar charts
 *
 * @component ProspectComparison
 * @param {ProspectComparisonProps} props - Component props
 * @returns {JSX.Element} Rendered comparison interface
 *
 * @example
 * ```tsx
 * <ProspectComparison
 *   prospects={[prospect1, prospect2]}
 *   onExport={handleExport}
 * />
 * ```
 */
export const ProspectComparison: React.FC<ProspectComparisonProps> = ({
  prospects,
  onExport,
  className
}) => {
  // Component implementation
};
```

#### Hook Documentation
```typescript
/**
 * Custom hook for managing prospect comparison state and operations
 *
 * @hook useProspectComparison
 * @param {string[]} prospectIds - Array of prospect IDs to compare
 * @returns {ProspectComparisonResult} Comparison data and control functions
 *
 * @example
 * ```tsx
 * const {
 *   comparison,
 *   isLoading,
 *   addProspect,
 *   removeProspect
 * } = useProspectComparison(['123', '456']);
 * ```
 */
```

### Python/FastAPI Standards

#### Function Documentation
```python
def calculate_prospect_similarity(
    prospect_a: ProspectData,
    prospect_b: ProspectData,
    weights: Optional[Dict[str, float]] = None
) -> SimilarityScore:
    """
    Calculate similarity score between two baseball prospects.

    Uses statistical analysis and ML embeddings to determine how similar
    two prospects are in terms of playing style and performance metrics.

    Args:
        prospect_a: First prospect's data including stats and metrics
        prospect_b: Second prospect's data for comparison
        weights: Optional dictionary of metric weights for custom scoring
                Default uses balanced weights across all categories

    Returns:
        SimilarityScore object containing overall score (0-1) and breakdown
        by category (hitting, fielding, speed, power)

    Raises:
        ValidationError: If prospect data is incomplete or invalid
        ModelError: If ML embeddings cannot be generated

    Example:
        >>> score = calculate_prospect_similarity(
        ...     prospect_data_1,
        ...     prospect_data_2,
        ...     weights={"hitting": 0.4, "fielding": 0.3, "speed": 0.3}
        ... )
        >>> print(f"Similarity: {score.overall:.2f}")
        Similarity: 0.87

    Note:
        This function requires ML models to be initialized. Call
        initialize_similarity_models() before first use.

    Since:
        1.0.0
    """
```

## File Organization Standards

### Directory Structure
```
apps/
├── web/                    # Next.js frontend
│   ├── src/
│   │   ├── app/           # App router pages
│   │   ├── components/    # Reusable components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── lib/          # Utility libraries
│   │   ├── types/        # TypeScript type definitions
│   │   └── __tests__/    # Test files
│   └── package.json
└── api/                   # FastAPI backend
    ├── app/
    │   ├── api/          # API route handlers
    │   ├── core/         # Core configuration
    │   ├── models/       # Database models
    │   ├── services/     # Business logic
    │   └── tests/        # Test files
    └── requirements.txt
```

### Import Organization
```typescript
// 1. Third-party imports
import React from 'react';
import { NextPage } from 'next';
import { useMutation } from '@tanstack/react-query';

// 2. Internal absolute imports
import { ProspectProfile } from '@/types/prospect';
import { apiClient } from '@/lib/api/client';

// 3. Relative imports
import { ProspectCard } from './ProspectCard';
import { useProspectData } from '../hooks/useProspectData';
```

## Testing Standards

### Test Documentation
```typescript
/**
 * @jest-environment jsdom
 */

describe('ProspectComparison Component', () => {
  /**
   * Test suite for prospect comparison functionality
   *
   * Covers rendering, data loading, user interactions, and error states
   * Tests both unit functionality and integration with prospect data services
   */

  describe('when comparing two prospects', () => {
    /**
     * Verifies that the component correctly displays comparison data
     * for two valid prospects with complete statistical information
     */
    it('should display comparison metrics correctly', async () => {
      // Test implementation
    });
  });
});
```

## Error Handling Standards

### Custom Error Classes
```typescript
/**
 * Base error class for prospect-related operations
 *
 * @class ProspectError
 * @extends {Error}
 */
export class ProspectError extends Error {
  /**
   * Creates a prospect-specific error
   *
   * @param message - Error message describing the issue
   * @param code - Error code for programmatic handling
   * @param prospectId - ID of the prospect related to the error
   */
  constructor(
    message: string,
    public readonly code: string,
    public readonly prospectId?: string
  ) {
    super(message);
    this.name = 'ProspectError';
  }
}
```

## Performance Standards

### Function Complexity
- Maximum cyclomatic complexity: 10
- Maximum function length: 50 lines
- Maximum parameter count: 5 (use options object for more)

### Documentation Performance
- All public APIs must include performance characteristics in JSDoc
- Database queries must document expected response times
- ML model calls must include typical inference times

```typescript
/**
 * Retrieves prospect rankings with pagination and filtering
 *
 * @performance
 * - Typical response time: 150-300ms for 25 results
 * - Database queries: 2-3 optimized queries with proper indexing
 * - Memory usage: ~2MB for standard result set
 *
 * @param filters - Search and filter criteria
 * @param pagination - Page size and offset information
 * @returns Promise resolving to paginated prospect rankings
 */
```

## Linting Configuration

### ESLint Rules (Enforced)
- `@typescript-eslint/explicit-function-return-type`: error
- `@typescript-eslint/no-explicit-any`: error
- `@typescript-eslint/no-unused-vars`: error
- `jsdoc/require-jsdoc`: error (for all public functions)
- `jsdoc/require-param-description`: error
- `jsdoc/require-returns-description`: error

### Pre-commit Hooks
- TypeScript compilation check
- ESLint with JSDoc validation
- Prettier formatting
- Import sorting
- Test execution for modified files

## Documentation Maintenance

### Version Control
- Update JSDoc `@since` tags for new features
- Mark breaking changes with `@deprecated` and migration notes
- Maintain changelog with API documentation updates

### Review Requirements
- All public API changes require documentation review
- JSDoc examples must be tested and validated
- Performance documentation must be verified with benchmarks

---

**Note**: This document is living and should be updated as the project evolves. All team members are responsible for maintaining these standards.