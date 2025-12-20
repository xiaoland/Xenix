# Column Selector Feature Documentation

## Overview

The Column Selector feature allows users to visually select which columns from their uploaded Excel file should be used as features (inputs) and which column should be the target (prediction variable). This eliminates the need for hardcoded column names and makes the platform work with any dataset structure.

## User Flow

### 1. Upload Excel File

```
┌─────────────────────────────────────┐
│  Click or drag file to upload      │
│                                     │
│     [📁 Upload Excel File]          │
│                                     │
│  Support: .xlsx, .xls files         │
└─────────────────────────────────────┘
        ↓
   [ Next: Select Columns ]
```

### 2. System Reads Column Names

The system automatically:
- Parses the uploaded Excel file
- Extracts column headers from the first row
- Validates that columns exist
- Displays them in the selector UI

### 3. Visual Column Selection

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│  Feature Columns                    │  Target Column                      │
│  (Checkbox - Multiple Selection)    │  (Radio - Single Selection)         │
├─────────────────────────────────────┼─────────────────────────────────────┤
│  ☑ age                              │  ○ age                              │
│  ☑ income                           │  ○ income                           │
│  ☑ credit_score                     │  ⦿ purchase_amount                  │
│  ☐ purchase_amount (disabled)       │  ○ credit_score (disabled)          │
│                                     │                                     │
│  Selected: 3 column(s)              │  ✓ Target: purchase_amount          │
└─────────────────────────────────────┴─────────────────────────────────────┘
        ↓
   [ Back to Upload ]  [ Confirm Selection ]
```

### 4. Validation & Proceed

- **Minimum requirements**: At least 1 feature column + 1 target column
- **Mutual exclusion**: Same column cannot be both feature and target
- **Real-time validation**: "Confirm" button disabled until valid
- **Visual feedback**: Shows count and status with colored tags

## Component Architecture

### ColumnSelector.vue

**Purpose**: Provides the visual interface for column selection

**Props**:
- `columns: string[]` - Array of column names from Excel file
- `featureColumns?: string[]` - Pre-selected features (optional)
- `targetColumn?: string` - Pre-selected target (optional)

**Events**:
- `back: []` - Triggered when user wants to re-upload file
- `confirm: [{ featureColumns: string[]; targetColumn: string }]` - Emits selections

**Features**:
- Checkbox group for features
- Radio group for target
- Automatic mutual exclusion
- Visual indicators (count, status tags)
- Hover effects for better UX
- Responsive grid layout

### UploadStep.vue

**Enhanced with 2-step flow**:

1. **File Upload**:
   - Drag & drop interface
   - File type validation (.xlsx, .xls only)
   - "Next: Select Columns" button

2. **Column Selection**:
   - Parses Excel file using `xlsx` library
   - Extracts column names from first row
   - Shows ColumnSelector component
   - "Back to Upload" and "Confirm Selection" buttons

**Dependencies**:
- `xlsx` library for Excel parsing
- `ant-design-vue` for UI components

## Technical Implementation

### Excel Parsing

```javascript
// Read the uploaded file
const file = fileList.value[0].originFileObj;
const arrayBuffer = await file.arrayBuffer();
const workbook = XLSX.read(arrayBuffer, { type: 'array' });

// Get the first sheet
const firstSheetName = workbook.SheetNames[0];
const worksheet = workbook.Sheets[firstSheetName];

// Extract column names from first row
const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
const columns = jsonData[0].filter(col => col !== null && col !== undefined);

// Convert to strings
const columnNames = columns.map(String);
```

### State Management (index.vue)

```javascript
// Store selected columns
const selectedFeatureColumns = ref<string[]>([]);
const selectedTargetColumn = ref<string>('');

// Handle column selection
const handleColumnSelection = ({ featureColumns, targetColumn }) => {
  selectedFeatureColumns.value = featureColumns;
  selectedTargetColumn.value = targetColumn;
  hasUploadedData.value = true;
};

// Pass to API
formData.append('featureColumns', JSON.stringify(featureColumns));
formData.append('targetColumn', targetColumn);
```

### API Integration

**Upload Endpoint** (`/api/upload`):
```typescript
// Receive from form data
const featureColumns = formData.get('featureColumns') as string;
const targetColumn = formData.get('targetColumn') as string;

// Parse JSON
const parsedFeatureColumns = JSON.parse(featureColumns);

// Pass to Python via stdin
const stdinData = {
  inputFile: "/uploads/data.xlsx",
  model: "Ridge",
  featureColumns: parsedFeatureColumns,
  targetColumn: targetColumn
};
```

**Prediction Endpoint** (`/api/predict`):
```typescript
// Same columns used for prediction
const featureColumns = formData.get('featureColumns') as string;
const targetColumn = formData.get('targetColumn') as string;
const parsedFeatureColumns = JSON.parse(featureColumns);

const stdinData = {
  trainingDataPath: trainingPath,
  predictionDataPath: predictionPath,
  model: selectedModel,
  params: paramsFromDB,
  featureColumns: parsedFeatureColumns,
  targetColumn: targetColumn
};
```

## UI Design

### Visual Elements

**Feature Column Panel** (Left):
- Icon: 🔷 Table column icon (blue)
- Title: "Feature Columns"
- Description: "Select columns to use as input features for model training"
- Controls: Checkbox group
- Footer: "Selected: X column(s)"

**Target Column Panel** (Right):
- Icon: 🎯 Target icon (green)
- Title: "Target Column"
- Description: "Select the column you want to predict (target variable)"
- Controls: Radio button group
- Footer: "✓ Target: column_name"

**Action Bar** (Bottom):
- Left: "← Back to Upload" button
- Center: Selection status tags
- Right: "Confirm Selection →" button (primary, disabled until valid)

### Color Coding

- **Blue**: Feature-related elements (icons, tags, borders)
- **Green**: Target-related elements (icons, tags, checkmarks)
- **Gray**: Disabled state, borders
- **White/Light**: Background, card surfaces

### Responsive Design

- **Desktop** (>768px): 2-column grid (features | target)
- **Mobile** (<768px): Stacked single column
- **Spacing**: Consistent padding and margins
- **Typography**: Font-mono for column names, sans-serif for UI text

## Error Handling

### User Errors

1. **No file uploaded**:
   - Button disabled
   - Tooltip: "Please upload a file first"

2. **Empty Excel file**:
   - Error message: "The Excel file appears to be empty"
   - Returns to upload step

3. **No column headers**:
   - Error message: "No column headers found in the Excel file"
   - Suggests checking file format

4. **Invalid selections**:
   - "Confirm" button disabled
   - Visual feedback: Tags show incomplete status
   - No error message (non-blocking)

### System Errors

1. **File parsing error**:
   - Error message: "Failed to read Excel file. Please make sure it has a valid format."
   - Logs error to console
   - Returns to upload step

2. **Network error**:
   - Handled by parent component
   - Shows API error messages

## Benefits

### For Users

✅ **No manual typing**: Visual selection is faster and error-free  
✅ **Works with any dataset**: No hardcoded column assumptions  
✅ **Clear feedback**: See exactly what's selected before proceeding  
✅ **Validation**: Prevents invalid configurations  
✅ **Flexibility**: Different datasets can use different columns  
✅ **Professional UI**: Clean, intuitive interface  

### For Developers

✅ **Separation of concerns**: UI handles selection, Python handles computation  
✅ **Type safety**: TypeScript ensures correct data flow  
✅ **Maintainability**: Modular components are easy to update  
✅ **Testability**: Components can be tested independently  
✅ **Extensibility**: Easy to add features (e.g., column preview, data types)  

## Future Enhancements

Potential improvements for future versions:

1. **Data Preview**: Show sample rows for selected columns
2. **Column Statistics**: Display data types, null counts, unique values
3. **Smart Suggestions**: Auto-suggest target based on column names/types
4. **Multi-target**: Support for multiple target columns (multi-output models)
5. **Column Filtering**: Search/filter columns by name
6. **Data Validation**: Check for missing values, outliers before training
7. **Save Configurations**: Remember column selections for similar datasets
8. **Bulk Selection**: Select/deselect all, select by pattern

## Example Use Cases

### Use Case 1: Customer Value Prediction

**Dataset**: Customer data with demographics and purchase history

**Columns**:
- `customer_id` (identifier)
- `age` (demographic)
- `income` (demographic)
- `credit_score` (financial)
- `purchase_history_count` (behavior)
- `total_spent_last_year` (behavior)
- `predicted_value` (target)

**Selection**:
- Features: age, income, credit_score, purchase_history_count, total_spent_last_year
- Target: predicted_value
- Excluded: customer_id (identifier, not useful for training)

### Use Case 2: House Price Prediction

**Dataset**: Real estate data

**Columns**:
- `address` (text)
- `square_feet` (numeric)
- `bedrooms` (numeric)
- `bathrooms` (numeric)
- `year_built` (numeric)
- `lot_size` (numeric)
- `price` (target)

**Selection**:
- Features: square_feet, bedrooms, bathrooms, year_built, lot_size
- Target: price
- Excluded: address (text identifier, not numeric)

### Use Case 3: Sales Forecasting

**Dataset**: Historical sales data

**Columns**:
- `date` (timestamp)
- `day_of_week` (categorical)
- `month` (categorical)
- `promotions_active` (boolean)
- `previous_week_sales` (numeric)
- `current_week_sales` (target)

**Selection**:
- Features: day_of_week, month, promotions_active, previous_week_sales
- Target: current_week_sales
- Excluded: date (will use derived features instead)

## API Reference

### ColumnSelector Component

```vue
<ColumnSelector
  :columns="['age', 'income', 'target']"
  :feature-columns="['age', 'income']"
  :target-column="'target'"
  @back="handleBack"
  @confirm="handleConfirm"
/>
```

**Props**:
- `columns: string[]` - **Required**. Array of column names from Excel
- `featureColumns?: string[]` - **Optional**. Pre-selected feature columns
- `targetColumn?: string` - **Optional**. Pre-selected target column

**Events**:
- `back: () => void` - User wants to return to file upload
- `confirm: (selection: { featureColumns: string[]; targetColumn: string }) => void` - User confirmed selection

**Computed**:
- `isValid: boolean` - True if at least 1 feature and 1 target selected

### UploadStep Component

```vue
<UploadStep
  v-model="fileList"
  @continue="handleColumnSelection"
/>
```

**Props**:
- `v-model: UploadFile[]` - **Required**. Ant Design upload file list

**Events**:
- `continue: (selection: { featureColumns: string[]; targetColumn: string }) => void` - Emitted after column selection

**Internal State**:
- `showColumnSelection: boolean` - Toggle between upload and column selection
- `excelColumns: string[]` - Extracted column names from Excel
- `isLoadingColumns: boolean` - Loading state during file parsing

## Dependencies

### Required Packages

```json
{
  "dependencies": {
    "xlsx": "^0.18.5",
    "ant-design-vue": "^4.2.6",
    "vue": "^3.5.25"
  }
}
```

### Installation

```bash
npm install xlsx
# or
pnpm add xlsx
```

## Testing

### Manual Testing Checklist

- [ ] Upload valid Excel file with headers
- [ ] System extracts columns correctly
- [ ] Select multiple feature columns
- [ ] Select single target column
- [ ] Cannot select same column as both
- [ ] "Confirm" button disabled when invalid
- [ ] "Back" button returns to upload
- [ ] Selections persist when navigating back
- [ ] Columns passed correctly to API
- [ ] Works with different datasets
- [ ] Error handling for empty files
- [ ] Error handling for files without headers
- [ ] Mobile responsive layout works

### Unit Testing (Future)

```typescript
// Example test cases
describe('ColumnSelector', () => {
  it('should render all columns', () => {
    // Test that all provided columns appear in UI
  });
  
  it('should enforce mutual exclusion', () => {
    // Test that selecting a target disables it in features
  });
  
  it('should validate selections', () => {
    // Test that isValid computed property works correctly
  });
  
  it('should emit correct selection on confirm', () => {
    // Test that confirm event contains correct data
  });
});
```

## Troubleshooting

### Issue: "No columns found"

**Cause**: Excel file might not have headers in first row

**Solution**: 
- Ensure first row contains column headers
- Check that cells are not empty or contain only spaces
- Verify file is not password-protected

### Issue: Column names appear as "Column1", "Column2"

**Cause**: First row is empty and xlsx library generated default names

**Solution**:
- Add proper headers to first row of Excel file
- Avoid merged cells in header row

### Issue: Some columns are missing

**Cause**: Columns with empty header cells are filtered out

**Solution**:
- Fill in all header cells in first row
- Remove completely empty columns from Excel file

### Issue: "Confirm" button stays disabled

**Cause**: Must select at least 1 feature AND 1 target

**Solution**:
- Check that you've selected checkboxes in left panel
- Check that you've selected a radio button in right panel
- Ensure selections are not conflicting (same column as both)

## Conclusion

The Column Selector feature provides a user-friendly way to configure dataset-specific settings without editing code. By visually selecting columns from uploaded Excel files, users can quickly set up their machine learning workflows and work with any dataset structure.

This feature is a key part of making Xenix a truly data-agnostic platform that can handle diverse use cases across different domains and industries.
