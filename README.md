# project-template

GitHub template for new personal projects. Includes the Claude PR review workflow out of the box.

## Use

```bash
gh repo create my-new-thing --template dirkknibbe/project-template --private
```

After cloning the new repo, set the `CLAUDE_CODE_OAUTH_TOKEN` repo secret:

```bash
gh -R dirkknibbe/my-new-thing secret set CLAUDE_CODE_OAUTH_TOKEN < ~/.config/claude/oauth-token
```
