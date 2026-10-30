import type { Finding } from "../types";

const RULE_LABEL: Record<string, string> = {
  over_category_cap: "over category cap",
  meals_daily_cap: "meals daily cap",
  missing_receipt: "missing receipt",
  missing_approval: "missing approval",
  suspected_duplicate: "suspected duplicate",
};

function money(amount: number, currency: string) {
  return `${currency} ${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function Findings({
  findings,
  currency,
}: {
  findings: Finding[];
  currency: string;
}) {
  return (
    <section className="card findings-card">
      <div className="card-head">
        <span className="card-index">03</span>
        <h3>Findings</h3>
        <span className="count">{findings.length}</span>
      </div>

      {findings.length === 0 ? (
        <p className="empty-line">No policy breaches in the rows that survived quarantine.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Rule</th>
                <th>Transactions</th>
                <th className="right">Amount</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((finding, index) => (
                <tr key={`${finding.rule}-${finding.txn_ids.join("-")}-${index}`}>
                  <td>
                    <span className={`sev sev--${finding.severity}`}>
                      <i aria-hidden="true" />
                      {finding.severity}
                    </span>
                  </td>
                  <td className="rule">{RULE_LABEL[finding.rule] ?? finding.rule}</td>
                  <td>
                    <span className="txns">
                      {finding.txn_ids.map((id) => (
                        <code key={id}>{id}</code>
                      ))}
                    </span>
                  </td>
                  <td className="right amount">{money(finding.amount, currency)}</td>
                  <td className="detail">{finding.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
