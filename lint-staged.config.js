// Runs on staged files only, via .husky/pre-commit.
// --force-exclude keeps ruff honoring extend-exclude (e.g. migrations) in pyproject.toml
// even when lint-staged passes those files explicitly.
module.exports = {
  "*.py": ["ruff check --fix --force-exclude", "ruff format --force-exclude"],
  // Model changes must ship with their migrations. The function form ignores the
  // file list so manage.py receives no extra arguments.
  "apps/**/{models.py,models/*.py}": () =>
    "python manage.py makemigrations --check --dry-run",
};
